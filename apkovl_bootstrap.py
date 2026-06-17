# vim: ts=4 et:

import io
import os
import subprocess
import tarfile
from pathlib import Path


class ApkovlBootstrap:
    """Generate the apkovl and SSH key used to bootstrap Packer over SSH."""

    SSH_KEY_NAME = "packer_ed25519"
    APKOVL_NAME = "packer.apkovl.tar.gz"

    def __init__(self, work_dir="work", key_comment="packer-apkovl-bootstrap"):
        self.work_dir = Path(work_dir)
        self.key_comment = key_comment

        self.ssh_dir = self.work_dir / "ssh"
        self.private_key = self.ssh_dir / self.SSH_KEY_NAME
        self.public_key = self.private_key.with_suffix(self.private_key.suffix + ".pub")

        self.apkovl_dir = self.work_dir / "apkovl"
        self.apkovl_path = self.apkovl_dir / self.APKOVL_NAME

    def prepare(self, force_apkovl=True):
        self.ensure_ssh_key()
        if force_apkovl or not self.apkovl_path.exists():
            self.write_apkovl()

    def ensure_ssh_key(self):
        self.ssh_dir.mkdir(parents=True, exist_ok=True)
        if self.private_key.exists() and self.public_key.exists():
            return

        if self.private_key.exists() or self.public_key.exists():
            raise RuntimeError(
                f"Refusing to overwrite partial SSH key pair: {self.private_key}"
            )

        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(self.private_key),
                "-C",
                self.key_comment,
            ],
            check=True,
        )

    def write_apkovl(self):
        self.apkovl_dir.mkdir(parents=True, exist_ok=True)
        public_key = self.public_key.read_text(encoding="utf8").strip()
        if not public_key:
            raise RuntimeError(f"Empty SSH public key: {self.public_key}")

        entries = [
            self._dir("etc"),
            self._dir("etc/network"),
            self._file("etc/network/interfaces", self._network_interfaces(), 0o644),
            self._dir("etc/local.d"),
            self._file("etc/local.d/packer-ssh.start", self._ssh_start(public_key), 0o755),
            self._dir("etc/runlevels"),
            self._dir("etc/runlevels/default"),
            self._symlink("etc/runlevels/default/local", "/etc/init.d/local"),
        ]

        tmp_path = self.apkovl_path.with_suffix(self.apkovl_path.suffix + ".tmp")
        with tarfile.open(tmp_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            for info, data in entries:
                tar.addfile(info, data)

        os.replace(tmp_path, self.apkovl_path)

    def _dir(self, name, mode=0o755):
        info = self._info(name.rstrip("/") + "/", tarfile.DIRTYPE, mode)
        return info, None

    def _file(self, name, content, mode):
        data = content.encode("utf8")
        info = self._info(name, tarfile.REGTYPE, mode)
        info.size = len(data)
        return info, io.BytesIO(data)

    def _symlink(self, name, target):
        info = self._info(name, tarfile.SYMTYPE, 0o777)
        info.linkname = target
        return info, None

    def _info(self, name, type_, mode):
        info = tarfile.TarInfo(name)
        info.type = type_
        info.mode = mode
        info.uid = 0
        info.gid = 0
        info.uname = "root"
        info.gname = "root"
        info.mtime = 0
        return info

    def _network_interfaces(self):
        return """auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
"""

    def _ssh_start(self, public_key):
        return f"""#!/bin/sh
set -eu

exec >/dev/console 2>&1
echo "packer-ssh: starting"

if ! command -v sshd >/dev/null 2>&1; then
    echo "packer-ssh: installing openssh"
    apk add --no-cache openssh
fi

ssh-keygen -A

mkdir -p /root/.ssh
cat > /root/.ssh/authorized_keys <<'EOF'
{public_key}
EOF
chmod 700 /root /root/.ssh
chmod 600 /root/.ssh/authorized_keys
chown -R root:root /root/.ssh

passwd -d root || true
sed -i 's/^root:[^:]*:/root::/' /etc/shadow

sed -i \\
    -e '/^PermitRootLogin /d' \\
    -e '/^PubkeyAuthentication /d' \\
    -e '/^AuthorizedKeysFile /d' \\
    -e '/^PasswordAuthentication /d' \\
    /etc/ssh/sshd_config
cat >> /etc/ssh/sshd_config <<'EOF'
PermitRootLogin yes
PubkeyAuthentication yes
AuthorizedKeysFile /root/.ssh/authorized_keys .ssh/authorized_keys
PasswordAuthentication no
EOF

rc-service networking start || true
rc-service sshd restart
echo "packer-ssh: ready"
"""
