# 01 — `kernel_cleanup`: old kernels removed by a retention policy

| | |
|---|---|
| Release | 1.0.0 (2026-11-20), the collection's first |
| PR | #1 `feature/kernel-cleanup`, merged as `2d90554` |
| Commits | `df5a5cd` bootstrap on `main`; `8f03033` skeleton; `1600858` module + tests; `db279f0` role, README, CHANGELOG |

## What

The module `aursu.baseprofile.kernel_cleanup` and a thin role of the same name.
They keep the newest kernels and the running one, and purge every package of
every other kernel. This is the Ansible counterpart of the Puppet profile
Alexander described: `baseprofile::kernel::cleanup` with `latest_only` and
`keep_last`, fed by an `installed_kernels` fact.

## Why — the goal

On `media-gw`, `/boot` (442 MB) held four kernels of ~105 MB each.
`unattended-upgrades` had been removed, so nothing ran autoremove, and a manual
`apt upgrade` added the fourth kernel. The next package install failed
rebuilding the initramfs ("No space left on device") and left `initramfs-tools`
half-configured. A one-off playbook with a hand-written list of 14 packages was
written and **rejected**: "this should be something systemic, not a patch".

Kernel updates now go only through Ansible, and the update play runs
`kernel_cleanup` before (room for the incoming kernel) and after.

## How it works

`KernelCleanup.run()`:

1. **Read.** `DebianKernelInventory(module).collect()` from `aursu.general`'s
   `module_utils/kernels.py` — the installed kernels, oldest first, each with its
   packages, releases, `running`, `latest`, `boot_bytes`. Read at the moment the
   module acts, never taken from an earlier task.
2. **Plan.** `RetentionPolicy(latest_only, keep_last).plan(kernels)`:
   - `keep_count` = 1 if `latest_only`, else `keep_last` (`keep_last < 1` is
     refused unless `latest_only`);
   - *bootable* = kernels that have a release (an image);
   - no bootable kernel at all → remove nothing (there is no "newest" to keep);
   - keep = the newest `keep_count` bootable kernels **plus the running one**;
   - remove = everything else, including leftovers without an image.
3. **Purge.** Unless in check mode: `apt-get -y purge <every package of every
   removed kernel>` with `DEBIAN_FRONTEND=noninteractive`; a non-zero exit fails
   the module with stdout/stderr.
4. **Verify.** Read the inventory again; if a removed version is still installed,
   fail.
5. **Report.** `changed`, `kept`, `removed`, `removed_packages`,
   `boot_bytes_freed`.

## Where it is defined

| File | What |
|---|---|
| `plugins/modules/kernel_cleanup.py` | `RetentionPolicy` (the plan, pure), `KernelCleanup` (read → plan → purge → verify → report), `main()` (argument spec: `latest_only`, `keep_last`, `boot_dir`) |
| `roles/kernel_cleanup/defaults/main.yml` | `kernel_cleanup_latest_only: false`, `kernel_cleanup_keep_last: 2` |
| `roles/kernel_cleanup/tasks/main.yml` | the module call and a summary message |
| `roles/kernel_cleanup/README.md` | variables and the `/boot` sizing rule |
| `tests/unit/plugins/modules/test_kernel_cleanup.py` | 14 tests: the policy, and the whole read-purge-verify cycle with a fake module |
| `galaxy.yml` | depends on `aursu.general >= 1.8.0` |
| `.github/workflows/*`, `.github/scripts/release_preflight.py` | unit tests, blocking lint, `ansible-doc`; release by tag |

## Rejected alternatives

- **A one-off playbook with a hard-coded package list.** Rejected by Alexander;
  also wrong on the next kernel series (7.0 brings `linux-main-modules-*`).
- **The module in `aursu.general`.** That collection is read-only by design;
  state-changing code gets its own collection — hence `aursu.baseprofile`.
- **Feeding `kernel_info`'s output into the module through the play.** The
  boundaries rule: a module that changes state reads the state itself.
- **Bringing back `unattended-upgrades`** with `Remove-Unused-Kernel-Packages`.
  Not chosen: updates are Ansible-only, so no kernel appears between runs.
- **A host-side timer with a shell copy of the logic.** A second implementation
  of the same rule, outside Ansible.
- **`MODULES=dep` for smaller initrds.** Kept as a possible addition; it ties the
  initrd to the current hardware.
- **`keep_last: 1` for `media-gw`.** Proposed first; the dry run showed it would
  remove the only fallback kernel (6.17.0-35). Alexander chose `keep_last: 2`
  (peak three sets ≈ 315 MB of 442).

## Release note

The first release run failed at Publish: the new repository had no
`GALAXY_API_KEY` secret. Galaxy never received the version, so the tag was not
spent; after the secret was added, a re-run published it.

## Verified by

14 unit tests against the published `aursu.general` 1.8.0; `ansible-lint`
clean (production profile); `ansible-doc`; pre-flight. Check mode on `media-gw`:
`keep_last=2` → remove 6.17.0-14/-20, 14 packages, 205 MB; `keep_last=1` →
three kernels, 21 packages, 309 MB. Applied with `keep_last: 2`: `/boot` 223M of
442M, `apt-get purge` also finished the half-configured `initramfs-tools` and
rebuilt the running kernel's initrd, `dpkg --audit` empty.

## Not covered

RPM-based systems.
