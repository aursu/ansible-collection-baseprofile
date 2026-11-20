# Changelog

All notable changes to `aursu.baseprofile` are documented here.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-20

### Added

- **Module `kernel_cleanup`** - removes old kernels by a retention policy: keep the newest
  `keep_last` kernels (default 2), or only the newest with `latest_only` (which wins), and always
  the running one. Purges every package carrying a removed kernel's ABI version with
  `apt-get purge`, then reads the inventory again and fails if a removed kernel is still there.
  Check mode reports what would be removed. Debian and Ubuntu.

  It reads the installed kernels itself, through `aursu.general`'s `module_utils/kernels.py`
  (hence `aursu.general >= 1.8.0`), never from a previous task's output.

  Why it exists: on 2026-11-20 a host with a 442 MB `/boot` held four kernels of ~105 MB each,
  and a package install failed rebuilding the initramfs with "No space left on device".

- **Role `kernel_cleanup`** - a thin wrapper with `kernel_cleanup_latest_only` and
  `kernel_cleanup_keep_last`.

- CI: unit tests, blocking `ansible-lint`, `ansible-doc` of every module; release by tag with
  the pre-flight from `aursu.lvm_setup`.

[1.0.0]: https://github.com/aursu/ansible-collection-baseprofile/releases/tag/v1.0.0
