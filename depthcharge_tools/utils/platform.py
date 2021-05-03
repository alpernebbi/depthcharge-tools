#! /usr/bin/env python3

import collections
import glob
import platform
import re
import shlex

from pathlib import Path

from depthcharge_tools.utils.subprocess import crossystem


def dt_compatibles():
    dt_model = Path("/proc/device-tree/compatible")
    if dt_model.exists():
        return dt_model.read_text().strip("\x00").split("\x00")


def dt_model():
    dt_model = Path("/proc/device-tree/model")
    if dt_model.exists():
        return dt_model.read_text().strip("\x00")


def cros_hwid():
    hwid_file = Path("/proc/device-tree/firmware/chromeos/hardware-id")
    if hwid_file.exists():
        return hwid_file.read_text().strip("\x00")

    # If we booted with e.g. u-boot, we don't have dt/firmware/chromeos
    return crossystem.hwid()


def os_release():
    os_release = {}

    os_release_f = Path("/etc/os-release")
    if os_release_f.exists():
        for line in os_release_f.read_text().splitlines():
            lhs, _, rhs = line.partition("=")
            os_release[lhs] = rhs.strip('\'"')

    return os_release


def kernel_cmdline():
    cmdline = ""

    cmdline_f = Path("/proc/cmdline")
    if cmdline_f.exists():
        cmdline = cmdline_f.read_text().rstrip("\n")

    return shlex.split(cmdline)


def is_cros_boot():
    dt_cros_firmware = Path("/proc/device-tree/firmware/chromeos")
    if dt_cros_firmware.is_dir():
        return True

    # Chrome OS firmware injects this into the kernel cmdline.
    if "cros_secure" in kernel_cmdline():
        return True

    return False


def root_requires_initramfs(root):
    x = "[0-9a-fA-F]"
    uuid = "{x}{{8}}-{x}{{4}}-{x}{{4}}-{x}{{4}}-{x}{{12}}".format(x=x)
    ntsig = "{x}{{8}}-{x}{{2}}".format(x=x)

    # Depthcharge replaces %U with an uuid, so we can use that as well.
    uuid = "({}|%U)".format(uuid)

    # Tries to validate the root=* kernel cmdline parameter.
    # See init/do_mounts.c in Linux tree.
    for pat in (
        "[0-9a-fA-F]{4}",
        "/dev/nfs",
        "/dev/[0-9a-zA-Z]+",
        "/dev/[0-9a-zA-Z]+[0-9]+",
        "/dev/[0-9a-zA-Z]+p[0-9]+",
        "PARTUUID=({uuid}|{ntsig})".format(uuid=uuid, ntsig=ntsig),
        "PARTUUID=({uuid}|{ntsig})/PARTNROFF=[0-9]+".format(
            uuid=uuid, ntsig=ntsig,
        ),
        "[0-9]+:[0-9]+",
        "PARTLABEL=.+",
        "/dev/cifs",
    ):
        if re.fullmatch(pat, root):
            return False

    return True


def vboot_keys(*keydirs, system=True):
    if len(keydirs) == 0 or system:
        keydirs = (
            *keydirs,
            "/usr/share/vboot/devkeys",
            "/usr/local/share/vboot/devkeys",
        )

    for keydir in keydirs:
        keydir = Path(keydir)
        if not keydir.is_dir():
            continue

        keyblock = keydir / "kernel.keyblock"
        signprivate = keydir / "kernel_data_key.vbprivk"
        signpubkey = keydir / "kernel_subkey.vbpubk"

        if not keyblock.exists():
            keyblock = None
        if not signprivate.exists():
            signprivate = None
        if not signpubkey.exists():
            signpubkey = None

        if keyblock or signprivate or signpubkey:
            return keydir, keyblock, signprivate, signpubkey

    return None, None, None, None


def installed_kernels():
    kernels = {}
    initrds = {}
    fdtdirs = {}

    def files(*patterns):
        for pattern in patterns:
            for path in glob.glob(pattern, recursive=True):
                path = Path(path)
                if path.is_file():
                    yield path

    def dirs(*patterns):
        for pattern in patterns:
            for path in glob.glob(pattern, recursive=True):
                path = Path(path)
                if path.is_dir():
                    yield path

    for f in files(
        "/boot/vmlinuz-*",
        "/boot/vmlinux-*",
    ):
        _, _, release = f.name.partition("-")
        kernels[release] = f

    for f in files(
        "/boot/vmlinuz",
        "/boot/vmlinux",
        "/vmlinuz",
        "/vmlinux",
        "/boot/Image",
        "/boot/zImage",
        "/boot/bzImage",
    ):
        kernels[None] = f
        break

    for f in files(
        "/boot/initrd-*",
        "/boot/initrd.img-*",
    ):
        _, _, release = f.name.partition("-")
        initrds[release] = f

    for f in files(
        "/boot/initrd.img",
        "/boot/initrd",
        "/boot/initramfs-linux.img",
        "/initrd.img",
        "/initrd",
    ):
        initrds[None] = f
        break

    for d in dirs(
        "/usr/lib/linux-image-*",
    ):
        _, _, release = d.name.partition("linux-image-")
        fdtdirs[release] = d

    for d in dirs(
        "/boot/dtbs/*",
    ):
        if d.name in kernels:
            fdtdirs[d.name] = d

    for d in dirs(
        "/boot/dtbs",
    ):
        # Duplicate dtb files means that the directory is split by
        # kernel release and we can't use it for a single release.
        dtbs = d.glob("**/*.dtb")
        counts = collections.Counter(dtb.name for dtb in dtbs)
        if all(c <= 1 for c in counts.values()):
            fdtdirs[None] = d
            break

    return [
        KernelEntry(
            release,
            kernel=kernels[release],
            initrd=initrds.get(release, None),
            fdtdir=fdtdirs.get(release, None),
        ) for release in kernels.keys()
    ]


class KernelEntry:
    def __init__(self, release, kernel, initrd=None, fdtdir=None):
        self.release = release
        self.kernel = kernel
        self.initrd = initrd
        self.fdtdir = fdtdir

    @property
    def description(self):
        os_name = os_release().get("NAME", None)

        if os_name is None:
            return "Linux {}".format(self.release)
        else:
            return "{}, with Linux {}".format(os_name, self.release)

    def _comparable_parts(self):
        pattern = "([^a-zA-Z0-9]?)([a-zA-Z]*)([0-9]*)"

        if self.release is None:
            return ()

        parts = []
        for sep, text, num in re.findall(pattern, self.release):
            # x.y.z > x.y-* == x.y* > x.y~*
            sep = {
                "~": -1,
                ".": 1,
            }.get(sep, 0)

            # x.y-* == x.y* > x.y > x.y-rc* == x.y-trunk*
            text = ({
                "rc": -1,
                "trunk": -1,
            }.get(text, 0), text)

            # Compare numbers as numbers
            num = int(num) if num else 0

            parts.append((sep, text, num))

        return tuple(parts)

    def __lt__(self, other):
        if not isinstance(other, KernelEntry):
            return NotImplemented

        return self._comparable_parts() < other._comparable_parts()

    def __gt__(self, other):
        if not isinstance(other, KernelEntry):
            return NotImplemented

        return self._comparable_parts() > other._comparable_parts()

    def __str__(self):
        return self.description

    def __repr__(self):
        return (
            "KernelEntry(release={!r}, kernel={!r}, initrd={!r}, fdtdir={!r})"
            .format(self.release, self.kernel, self.initrd, self.fdtdir)
        )


class Architecture(str):
    arm_32 = ["arm"]
    arm_64 = ["arm64", "aarch64"]
    arm = arm_32 + arm_64
    x86_32 = ["i386", "x86"]
    x86_64 = ["x86_64", "amd64"]
    x86 = x86_32 + x86_64
    all = arm + x86
    groups = (arm_32, arm_64, x86_32, x86_64)

    def __eq__(self, other):
        if isinstance(other, Architecture):
            for group in self.groups:
                if self in group and other in group:
                    return True
        return str(self) == str(other)

    def __ne__(self, other):
        if isinstance(other, Architecture):
            for group in self.groups:
                if self in group and other not in group:
                    return True
        return str(self) != str(other)

    @property
    def mkimage(self):
        if self in self.arm_32:
            return "arm"
        if self in self.arm_64:
            return "arm64"
        if self in self.x86_32:
            return "x86"
        if self in self.x86_64:
            return "x86_64"

    @property
    def vboot(self):
        if self in self.arm_32:
            return "arm"
        if self in self.arm_64:
            return "aarch64"
        if self in self.x86_32:
            return "x86"
        if self in self.x86_64:
            return "amd64"
