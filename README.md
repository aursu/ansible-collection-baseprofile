# Ansible Collection - aursu.baseprofile

Base configuration of a host: modules and roles that **change** state, the
counterpart of the read-only facts collection `aursu.general`.

The first content - `kernel_cleanup`, removal of old kernels by policy
(`latest_only` / `keep_last`) - is under review. See the pull requests.
