# CHANGELOG

## 2026-06-17

### Updates

- Config updates for releasing 3.24.
- Drop explicit creation of NoCloud and OCI images, please use Generic images instead. [#190](https://gitlab.alpinelinux.org/alpine/cloud/alpine-cloud-images/-/work_items/190)

### Changed

- Reworked QEMU local image builds to boot Alpine directly with cached kernel/initrd artifacts and an apkovl-based SSH bootstrap, replacing the previous VNC `boot_command` SSH setup flow.
- Reuse cached QEMU builder boot assets, apkovl data, generated SSH keys, and firmware under `work/` until refreshed with `--clean`.
- Updated GCP `raw.tar.gz` conversion to run as explicit conversion, resize, and archive steps.
- Resize GCP raw images based on resolved `disk_size`, rounded up to whole GiB.
- Generate GCP `raw.tar.gz` archives with Python `tarfile.GNU_FORMAT` instead of requiring external `gtar`. [#175](https://gitlab.alpinelinux.org/alpine/cloud/alpine-cloud-images/-/work_items/175)
- Parallelized `get-image-cache.py` region collection with `--parallel N`.
- Parallelized `prune-images.py` region pruning with `--parallel N`.
- Documented `build --not-regions`, QEMU apkovl bootstrapping, helper parallelism, and `raw.tar.gz` conversion behavior.

### Fixed

- Add `mana` and `pci-hyperv` drivers for Azure and Generic images. [#188](https://gitlab.alpinelinux.org/alpine/cloud/alpine-cloud-images/-/work_items/188)
- Add wired network firmware drivers for metal inages. [#189](https://gitlab.alpinelinux.org/alpine/cloud/alpine-cloud-images/-/work_items/189)
- Fixed aarch64 QEMU local builds failing when Packer VNC keystrokes did not reach the VM.
- Fixed missing builder boot modules needed for target image filesystem creation and EFI partition mounting.
- Fixed `raw.tar.gz` conversion diagnostics by splitting the previous shell pipeline into separate steps.
- Fixed `get-image-cache.py` latest-image revision comparison logic.
