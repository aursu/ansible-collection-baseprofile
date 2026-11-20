# Ansible Role: kernel_cleanup

Removes old kernels by a retention policy, so that `/boot` does not fill up.
A thin wrapper over the module `aursu.baseprofile.kernel_cleanup`, which reads
the installed kernels itself (through `aursu.general`'s kernel inventory),
purges every package of every kernel outside the policy, and verifies.

The running kernel is never removed.

## Variables

| Variable | Default | Meaning |
|---|---|---|
| `kernel_cleanup_latest_only` | `false` | Keep only the newest kernel and the running one. Wins over `keep_last`. |
| `kernel_cleanup_keep_last` | `2` | Otherwise keep this many newest kernels, plus the running one. |

## Sizing

Installing a kernel needs room for one more set before the old ones are
removed. With about 105 MB per kernel set (Ubuntu 24.04, `MODULES=most`), a
442 MB `/boot` fits `keep_last: 2` plus the incoming one, but not four.

## Example

```yaml
- hosts: all
  become: true
  roles:
    - role: aursu.baseprofile.kernel_cleanup
      vars:
        kernel_cleanup_keep_last: 1
```

Debian and Ubuntu for now.
