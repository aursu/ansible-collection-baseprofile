#!/usr/bin/python
# -*- coding: utf-8 -*-
# pyright: reportMissingImports=false
# pylint: disable=import-error

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.aursu.baseprofile.plugins.modules import kernel_cleanup
from ansible_collections.aursu.baseprofile.plugins.modules.kernel_cleanup import RetentionPolicy

KERNELS_MOD = 'ansible_collections.aursu.general.plugins.module_utils.kernels'


def kernel(version, running=False, image=True):
    return {'version': version, 'releases': ['%s-generic' % version] if image else [],
            'packages': ['linux-image-%s-generic' % version], 'running': running,
            'latest': False, 'boot_bytes': 100}


# Oldest first, as the inventory returns it; the newest is running.
FOUR = [kernel('6.17.0-14'), kernel('6.17.0-20'), kernel('6.17.0-35'), kernel('7.0.0-43', running=True)]


def versions(kernels):
    return [k['version'] for k in kernels]


class TestRetentionPolicy(unittest.TestCase):

    def test_keep_last_two(self):
        kept, removed = RetentionPolicy(False, 2).plan(FOUR)
        self.assertEqual(versions(kept), ['6.17.0-35', '7.0.0-43'])
        self.assertEqual(versions(removed), ['6.17.0-14', '6.17.0-20'])

    def test_latest_only_wins_over_keep_last(self):
        kept, removed = RetentionPolicy(True, 5).plan(FOUR)
        self.assertEqual(versions(kept), ['7.0.0-43'])
        self.assertEqual(len(removed), 3)

    def test_running_kernel_is_kept_even_when_old(self):
        # Not rebooted after an upgrade: the running kernel is not the newest.
        kernels = [kernel('6.17.0-20'), kernel('6.17.0-35', running=True), kernel('7.0.0-43')]
        kept, removed = RetentionPolicy(True, 1).plan(kernels)
        self.assertEqual(versions(kept), ['6.17.0-35', '7.0.0-43'])
        self.assertEqual(versions(removed), ['6.17.0-20'])

    def test_leftovers_without_an_image_are_removed(self):
        kernels = [kernel('6.17.0-9', image=False)] + FOUR
        _, removed = RetentionPolicy(False, 2).plan(kernels)
        self.assertIn('6.17.0-9', versions(removed))

    def test_nothing_is_removed_without_a_bootable_kernel(self):
        kernels = [kernel('6.17.0-9', image=False)]
        self.assertEqual(RetentionPolicy(True, 1).plan(kernels), (kernels, []))

    def test_fewer_kernels_than_keep_last_removes_nothing(self):
        self.assertEqual(RetentionPolicy(False, 10).plan(FOUR)[1], [])

    def test_keep_last_below_one_is_refused(self):
        with self.assertRaises(ValueError):
            RetentionPolicy(False, 0)

    def test_keep_last_is_irrelevant_when_latest_only(self):
        self.assertEqual(RetentionPolicy(True, 0).keep_count, 1)


DPKG_BEFORE = ''.join('linux-image-%s-generic\tii \nlinux-modules-%s-generic\tii \n' % (v, v)
                      for v in ('6.17.0-14', '6.17.0-20', '6.17.0-35', '7.0.0-43'))
DPKG_AFTER = ''.join('linux-image-%s-generic\tii \nlinux-modules-%s-generic\tii \n' % (v, v)
                     for v in ('6.17.0-35', '7.0.0-43'))


class TestModule(unittest.TestCase):
    """The whole cycle: read, plan, purge, read again, verify."""

    def _run(self, outputs, check_mode=False, params=None):
        with patch('%s.AnsibleModule' % kernel_cleanup.__name__) as ansible_module, \
             patch('%s.os.uname' % KERNELS_MOD, return_value=('Linux', 'h', '7.0.0-43-generic', '', 'x86_64')):
            module = MagicMock()
            module.params = dict({'latest_only': False, 'keep_last': 2, 'boot_dir': '/nonexistent-boot'},
                                 **(params or {}))
            module.check_mode = check_mode
            module.get_bin_path.side_effect = lambda name, required=False: '/usr/bin/' + name
            module.run_command.side_effect = outputs
            module.fail_json.side_effect = SystemExit
            ansible_module.return_value = module
            try:
                kernel_cleanup.main()
            except SystemExit:
                pass
            return module

    def commands(self, module):
        return [call.args[0] for call in module.run_command.call_args_list]

    def test_purges_the_old_kernels_and_verifies(self):
        module = self._run([(0, DPKG_BEFORE, ''), (0, '', ''), (0, DPKG_AFTER, '')])
        purge = self.commands(module)[1]
        self.assertEqual(purge[:3], ['/usr/bin/apt-get', '-y', 'purge'])
        self.assertEqual(sorted(purge[3:]), [
            'linux-image-6.17.0-14-generic', 'linux-image-6.17.0-20-generic',
            'linux-modules-6.17.0-14-generic', 'linux-modules-6.17.0-20-generic'])
        result = module.exit_json.call_args.kwargs
        self.assertTrue(result['changed'])
        self.assertEqual(result['removed'], ['6.17.0-14', '6.17.0-20'])
        self.assertEqual(result['kept'], ['6.17.0-35', '7.0.0-43'])

    def test_check_mode_reports_and_does_not_purge(self):
        module = self._run([(0, DPKG_BEFORE, '')], check_mode=True)
        self.assertEqual(len(self.commands(module)), 1)
        self.assertEqual(module.exit_json.call_args.kwargs['removed'], ['6.17.0-14', '6.17.0-20'])

    def test_nothing_to_remove_reports_no_change(self):
        module = self._run([(0, DPKG_AFTER, '')])
        self.assertEqual(len(self.commands(module)), 1)
        self.assertFalse(module.exit_json.call_args.kwargs['changed'])

    def test_a_kernel_still_installed_after_purge_fails(self):
        module = self._run([(0, DPKG_BEFORE, ''), (0, '', ''), (0, DPKG_BEFORE, '')])
        self.assertIn('still installed', module.fail_json.call_args.kwargs['msg'])
        module.exit_json.assert_not_called()

    def test_a_failed_purge_fails(self):
        module = self._run([(0, DPKG_BEFORE, ''), (100, '', 'E: no space')])
        self.assertEqual(module.fail_json.call_args.kwargs['msg'], 'apt-get purge failed')

    def test_keep_last_zero_fails(self):
        module = self._run([], params={'keep_last': 0})
        self.assertIn('keep_last', module.fail_json.call_args.kwargs['msg'])


if __name__ == '__main__':
    unittest.main()
