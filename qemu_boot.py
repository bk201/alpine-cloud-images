# vim: ts=4 et:

import hashlib
import os
import shutil
import subprocess
import tempfile

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


class QemuBoot:
    """Prepare latest Alpine virt ISO boot artifacts for Packer QEMU builds."""

    APPEND_MODULES = "loop,squashfs,sd-mod,usb-storage,virtio_net,virtio_pci,virtio_blk,ext4,fat,vfat,nls_cp437,nls_iso8859-1,nls_utf8"
    ISO_NAME = "alpine-virt.iso"
    CONSOLE = {
        "aarch64": "ttyAMA0",
        "x86_64": "ttyS0",
    }

    def __init__(self, work_dir="work", alpine=None):
        if alpine is None:
            raise ValueError("alpine helper is required")

        self.work_dir = Path(work_dir)
        self.alpine = alpine
        self.boot_dir = self.work_dir / "boot"

    def install(self, arches):
        if self.boot_dir.is_dir():
            return

        for arch in arches:
            self.prepare_arch(arch)

    def prepare_arch(self, arch):
        if arch not in self.CONSOLE:
            raise ValueError(f"unsupported QEMU boot arch: {arch}")

        iso_url = self.alpine.virt_iso_url(arch=arch)
        out_dir = self.boot_dir / f"latest-{arch}"
        out_dir.mkdir(parents=True, exist_ok=True)

        iso_path = out_dir / self.ISO_NAME
        self._stage_iso(iso_url, iso_path)
        self._write_checksum(iso_path)

        kernel = out_dir / "vmlinuz-virt"
        initrd = out_dir / "initramfs-virt"
        self._extract_boot_files(iso_path, kernel, initrd)

        return {
            "builder_iso_url": str(iso_path),
            "kernel": str(kernel),
            "initrd": str(initrd),
            "append": self.append_args(arch),
        }

    def append_args(self, arch):
        if arch not in self.CONSOLE:
            raise ValueError(f"unsupported QEMU boot arch: {arch}")

        return (
            f"modules={self.APPEND_MODULES} "
            f"console={self.CONSOLE[arch]} "
            "ip=dhcp "
            "apkovl=http://{{ .HTTPIP }}:{{ .HTTPPort }}/packer.apkovl.tar.gz"
        )

    def _stage_iso(self, iso_url, iso_path):
        tmp_path = iso_path.with_suffix(iso_path.suffix + ".tmp")
        tmp_path.unlink(missing_ok=True)

        parsed = urlparse(iso_url)
        if parsed.scheme in ("", "file"):
            src = Path(parsed.path if parsed.scheme == "file" else iso_url)
            shutil.copy2(src, tmp_path)
        else:
            with urlopen(iso_url) as src, open(tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        os.replace(tmp_path, iso_path)

    def _write_checksum(self, iso_path):
        checksum_path = Path(str(iso_path) + ".sha512")
        checksum = hashlib.sha512()
        with open(iso_path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                checksum.update(block)

        checksum_path.write_text(
            f"{checksum.hexdigest()}  {iso_path.name}\n",
            encoding="utf8",
        )

    def _extract_boot_files(self, iso_path, kernel, initrd):
        out_dir = kernel.parent
        with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
            tmp = Path(tmp)
            subprocess.run(
                [
                    "bsdtar",
                    "-xf",
                    str(iso_path),
                    "-C",
                    str(tmp),
                    "boot/vmlinuz-virt",
                    "boot/initramfs-virt",
                ],
                check=True,
            )
            os.replace(tmp / "boot" / "vmlinuz-virt", kernel)
            os.replace(tmp / "boot" / "initramfs-virt", initrd)
