# Ansible Collection - aursu.baseprofile

Base configuration of a host: modules and roles that **change** state, the
counterpart of the read-only facts collection `aursu.general`. A module here
reads the state it needs itself, at the moment it acts, through `aursu.general`'s
`module_utils` - never from an earlier task's registered output.

## Content

| Kind | Name | What |
|---|---|---|
| module | `kernel_cleanup` | Remove old kernels by policy: `latest_only` or `keep_last: N`, always keeping the running one; verifies after purging. |
| role | `kernel_cleanup` | Thin wrapper: `kernel_cleanup_latest_only`, `kernel_cleanup_keep_last`. See `roles/kernel_cleanup/README.md`. |

## Requirements

- `aursu.general >= 1.8.0` (declared in `galaxy.yml`).
- Debian or Ubuntu for `kernel_cleanup`.

## Testing

```sh
mkdir -p /tmp/c/ansible_collections/aursu && ln -s "$PWD" /tmp/c/ansible_collections/aursu/baseprofile
ansible-galaxy collection install "aursu.general:==1.8.0" -p /tmp/c
cd /tmp/c/ansible_collections/aursu/baseprofile && PYTHONPATH=/tmp/c python -m pytest tests/unit -q
```
