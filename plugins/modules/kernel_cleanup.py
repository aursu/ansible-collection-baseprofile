#!/usr/bin/python
# -*- coding: utf-8 -*-

#  Copyright (c) 2026 Alexander Ursu <alexander.ursu@gmail.com>
#  MIT License (see LICENSE file or https://opensource.org/licenses/MIT)
#  SPDX-License-Identifier: MIT

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r"""
module: kernel_cleanup

short_description: Remove old kernels by a retention policy

version_added: "1.0.0"

description:
  - Keeps the newest kernels and the running one, and purges every package of every other
    kernel - image, modules, headers, tools, whatever carries its ABI version.
  - Reads the installed kernels itself, at the moment it acts, through
    C(aursu.general.plugins.module_utils.kernels); it never takes them from a previous task.
  - The running kernel is never removed, whatever the policy says.
  - Kernels whose packages carry no image (leftover headers or tools) are removed unless their
    version is kept.
  - When no installed kernel has an image, nothing is removed - there is nothing to measure
    "newest" against.
  - After removing, reads the inventory again and fails if a removed kernel is still installed.
  - Debian and Ubuntu (C(apt-get purge)) for now.

options:
  latest_only:
    description:
      - Keep only the newest kernel (and the running one). Takes precedence over O(keep_last).
    type: bool
    default: false
  keep_last:
    description:
      - Number of newest kernels with an image to keep, in addition to the running one.
      - Ignored when O(latest_only=true).
    type: int
    default: 2
  boot_dir:
    description:
      - Directory holding the kernel images; used to report the space freed.
    type: path
    default: /boot

notes:
  - Supports check mode, reporting what would be removed.
  - Kernel ordering is numeric on the ABI version (6.17.0-9 before 6.17.0-14).

author:
  - Alexander Ursu (@aursu)
"""

EXAMPLES = r"""
- name: Keep the newest kernel and the running one
  aursu.baseprofile.kernel_cleanup:
    latest_only: true

- name: Keep the two newest kernels and the running one
  aursu.baseprofile.kernel_cleanup:
    keep_last: 2
"""

RETURN = r"""
kept:
  description: Versions kept, oldest first.
  returned: always
  type: list
  elements: str
  sample: [6.17.0-35, 7.0.0-43]
removed:
  description: Versions removed (or, in check mode, that would be), oldest first.
  returned: always
  type: list
  elements: str
  sample: [6.17.0-14, 6.17.0-20]
removed_packages:
  description: Every package purged.
  returned: always
  type: list
  elements: str
boot_bytes_freed:
  description: Size of the removed kernels' files in O(boot_dir).
  returned: always
  type: int
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.aursu.general.plugins.module_utils.kernels import DebianKernelInventory


class RetentionPolicy:
    """Which kernels to keep: the newest N with an image, and the running one."""

    def __init__(self, latest_only, keep_last):
        if not latest_only and keep_last < 1:
            raise ValueError('keep_last must be at least 1, got %d' % keep_last)
        self.keep_count = 1 if latest_only else keep_last

    def plan(self, kernels):
        """Split an oldest-first inventory into (kept, removed)."""
        bootable = [kernel for kernel in kernels if kernel['releases']]
        if not bootable:
            return list(kernels), []
        keep = {kernel['version'] for kernel in bootable[-self.keep_count:]}
        keep.update(kernel['version'] for kernel in kernels if kernel['running'])
        kept = [kernel for kernel in kernels if kernel['version'] in keep]
        removed = [kernel for kernel in kernels if kernel['version'] not in keep]
        return kept, removed


class KernelCleanup:
    """Reads the installed kernels, applies the policy, purges, verifies."""

    def __init__(self, module):
        self.module = module
        self.inventory = DebianKernelInventory(module, boot_dir=module.params['boot_dir'])
        try:
            self.policy = RetentionPolicy(module.params['latest_only'], module.params['keep_last'])
        except ValueError as error:
            module.fail_json(msg=str(error))

    def purge(self, packages):
        command = [self.module.get_bin_path('apt-get', required=True), '-y', 'purge'] + packages
        rc, out, err = self.module.run_command(command, environ_update={'DEBIAN_FRONTEND': 'noninteractive'})
        if rc != 0:
            self.module.fail_json(msg='apt-get purge failed', rc=rc, stdout=out, stderr=err, packages=packages)

    def verify(self, removed):
        still = sorted({kernel['version'] for kernel in self.inventory.collect()}
                       & {kernel['version'] for kernel in removed})
        if still:
            self.module.fail_json(msg='kernels still installed after purge: %s' % ', '.join(still))

    def run(self):
        kept, removed = self.policy.plan(self.inventory.collect())
        packages = sorted(package for kernel in removed for package in kernel['packages'])
        if removed and not self.module.check_mode:
            self.purge(packages)
            self.verify(removed)
        self.module.exit_json(
            changed=bool(removed),
            kept=[kernel['version'] for kernel in kept],
            removed=[kernel['version'] for kernel in removed],
            removed_packages=packages,
            boot_bytes_freed=sum(kernel['boot_bytes'] for kernel in removed),
        )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            latest_only=dict(type='bool', default=False),
            keep_last=dict(type='int', default=2),
            boot_dir=dict(type='path', default='/boot'),
        ),
        supports_check_mode=True,
    )
    module.run_command_environ_update = {
        'LANG': 'C', 'LC_ALL': 'C', 'LC_MESSAGES': 'C', 'LC_CTYPE': 'C',
    }
    KernelCleanup(module).run()


if __name__ == '__main__':
    main()
