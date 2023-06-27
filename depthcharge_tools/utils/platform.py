#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools platform utilities
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import collections
import glob
import platform
import re
import shlex

from pathlib import Path

from depthcharge_tools.utils.pathlib import (
    decompress,
)
from depthcharge_tools.utils.subprocess import (
    crossystem,
)


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

    for hwid_file in Path("/sys/bus/platform/devices").glob("GGL0001:*/HWID"):
        if hwid_file.exists():
            return hwid_file.read_text().strip()

    # Try crossystem as a last resort
    try:
        return crossystem.hwid()
    except:
        pass


def cros_fwid():
    fwid_file = Path("/proc/device-tree/firmware/chromeos/firmware-version")
    if fwid_file.exists():
        return fwid_file.read_text().strip("\x00")

    for fwid_file in Path("/sys/bus/platform/devices").glob("GGL0001:*/FWID"):
        if fwid_file.exists():
            return fwid_file.read_text().strip()

    # Try crossystem as a last resort
    try:
        return crossystem.fwid()
    except:
        pass


def os_release(root=None):
    os_release = {}

    if root is None:
        root = "/"
    root = Path(root).resolve()

    os_release_f = root / "etc" / "os-release"
    if not os_release_f.exists():
        os_release_f = root / "usr" / "lib" / "os-release"

    if os_release_f.exists():
        for line in os_release_f.read_text().splitlines():
            lhs, _, rhs = line.partition("=")
            os_release[lhs] = rhs.strip('\'"')

    return os_release


def kernel_cmdline(root=None):
    cmdline = ""

    if root is None:
        root = "/"
    root = Path(root).resolve()

    cmdline_f = root / "etc" / "kernel" / "cmdline"
    if not cmdline_f.exists():
        cmdline_f = root / "usr" / "lib" / "kernel" / "cmdline"

    if cmdline_f.exists():
        cmdline = cmdline_f.read_text().rstrip("\n")

    return shlex.split(cmdline)


def proc_cmdline():
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
    if "cros_secure" in proc_cmdline():
        return True

    return False


def is_cros_libreboot():
    fwid = cros_fwid()
    if fwid is None:
        return False

    return fwid.lower().startswith("libreboot")


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


def vboot_keys(*keydirs, system=True, root=None):
    if len(keydirs) == 0 or system:
        if root is None:
            root = "/"
        root = Path(root).resolve()

        keydirs = (
            *keydirs,
            root / "etc" / "depthcharge-tools",
            root / "usr" / "share" / "vboot" / "devkeys",
            root / "usr" / "local" / "share" / "vboot" / "devkeys",
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


def cpu_microcode(boot=None):
    microcode = []

    for f in (
        *boot.glob("amd-ucode.img"),
        *boot.glob("amd-uc.img"),
    ):
        if f.is_file():
            microcode.append(f)
            break

    for f in (
        *boot.glob("intel-ucode.img"),
        *boot.glob("intel-uc.img"),
    ):
        if f.is_file():
            microcode.append(f)
            break

    if not microcode:
        for f in (
            *boot.glob("early_ucode.cpio"),
            *boot.glob("microcode.cpio"),
        ):
            if f.is_file():
                microcode.append(f)
                break

    return microcode


def installed_kernels(root=None, boot=None):
    kernels = {}
    initrds = {}
    fdtdirs = {}

    if root is None:
        root = "/"
    root = Path(root).resolve()

    if boot is None:
        boot = root / "boot"
    boot = Path(boot).resolve()

    for f in (
        *root.glob("lib/modules/*/vmlinuz"),
        *root.glob("lib/modules/*/vmlinux"),
        *root.glob("lib/modules/*/Image"),
        *root.glob("lib/modules/*/zImage"),
        *root.glob("lib/modules/*/bzImage"),
        *root.glob("usr/lib/modules/*/vmlinuz"),
        *root.glob("usr/lib/modules/*/vmlinux"),
        *root.glob("usr/lib/modules/*/Image"),
        *root.glob("usr/lib/modules/*/zImage"),
        *root.glob("usr/lib/modules/*/bzImage"),
    ):
        if not f.is_file():
            continue
        release = f.parent.name
        kernels[release] = f.resolve()

    for f in (
        *boot.glob("vmlinuz-*"),
        *boot.glob("vmlinux-*"),
    ):
        if not f.is_file():
            continue
        _, _, release = f.name.partition("-")
        kernels[release] = f.resolve()

    for f in (
        *boot.glob("vmlinuz"),
        *boot.glob("vmlinux"),
        *root.glob("vmlinuz"),
        *root.glob("vmlinux"),
        *boot.glob("Image"),
        *boot.glob("zImage"),
        *boot.glob("bzImage"),
    ):
        if not f.is_file():
            continue
        kernels[None] = f.resolve()
        break

    for f in (
        *root.glob("lib/modules/*/initrd"),
        *root.glob("lib/modules/*/initramfs"),
        *root.glob("lib/modules/*/initrd.img"),
        *root.glob("lib/modules/*/initramfs.img"),
        *root.glob("usr/lib/modules/*/initrd"),
        *root.glob("usr/lib/modules/*/initramfs"),
        *root.glob("usr/lib/modules/*/initrd.img"),
        *root.glob("usr/lib/modules/*/initramfs.img"),
    ):
        if not f.is_file():
            continue
        release = f.parent.name
        initrds[release] = f.resolve()

    for f in (
        *boot.glob("initrd-*.img"),
        *boot.glob("initramfs-*.img"),
    ):
        if not f.is_file():
            continue
        _, _, release = f.name.partition("-")
        release = release[:-4]
        initrds[release] = f.resolve()

    for f in (
        *boot.glob("initrd-*"),
        *boot.glob("initrd.img-*"),
        *boot.glob("initramfs-*"),
        *boot.glob("initramfs.img-*"),
    ):
        if not f.is_file():
            continue
        _, _, release = f.name.partition("-")
        initrds[release] = f.resolve()

    for f in (
        *boot.glob("initrd.img"),
        *boot.glob("initrd"),
        *boot.glob("initramfs-linux.img"),
        *boot.glob("initramfs-vanilla"),
        *boot.glob("initramfs"),
        *root.glob("initrd.img"),
        *root.glob("initrd"),
        *root.glob("initramfs"),
    ):
        if not f.is_file():
            continue
        initrds[None] = f.resolve()
        break

    for d in (
        *root.glob("usr/lib/linux-image-*"),
    ):
        if not d.is_dir():
            continue
        _, _, release = d.name.partition("linux-image-")
        fdtdirs[release] = d.resolve()

    for d in (
        *root.glob("lib/modules/*/dtb"),
        *root.glob("lib/modules/*/dtbs"),
        *root.glob("usr/lib/modules/*/dtb"),
        *root.glob("usr/lib/modules/*/dtbs"),
    ):
        if not d.is_dir():
            continue
        release = d.parent.name
        fdtdirs[release] = d.resolve()

    for d in (
        *boot.glob("dtb-*"),
        *boot.glob("dtbs-*"),
    ):
        if not d.is_dir():
            continue
        _, _, release = d.name.partition("-")
        fdtdirs[release] = d.resolve()

    for d in (
        *boot.glob("dtb/*"),
        *boot.glob("dtbs/*"),
    ):
        if not d.is_dir():
            continue
        if d.name in kernels:
            fdtdirs[d.name] = d.resolve()

    for d in (
        *boot.glob("dtbs"),
        *boot.glob("dtb"),
        *root.glob("usr/share/dtbs"),
        *root.glob("usr/share/dtb"),
    ):
        if not d.is_dir():
            continue
        # Duplicate dtb files means that the directory is split by
        # kernel release and we can't use it for a single release.
        dtbs = d.glob("**/*.dtb")
        counts = collections.Counter(dtb.name for dtb in dtbs)
        if all(c <= 1 for c in counts.values()):
            fdtdirs[None] = d.resolve()
            break

    if None in kernels:
        kernel, release = kernels[None], None
        for r, k in kernels.items():
            if k == kernel and r is not None:
                release = r
                break

        if release is not None:
            del kernels[None]
            if None in initrds:
                initrds.setdefault(release, initrds[None])
                del initrds[None]
            if None in fdtdirs:
                fdtdirs.setdefault(release, fdtdirs[None])
                del fdtdirs[None]

    return [
        KernelEntry(
            release,
            kernel=kernels[release],
            initrd=initrds.get(release, None),
            fdtdir=fdtdirs.get(release, None),
            os_name=os_release(root=root).get("NAME", None),
        ) for release in kernels.keys()
    ]


class KernelEntry:
    def __init__(self, release, kernel, initrd=None, fdtdir=None, os_name=None):
        self.release = release
        self.kernel = kernel
        self.initrd = initrd
        self.fdtdir = fdtdir
        self.os_name = os_name

    @property
    def description(self):
        if self.os_name is None:
            return "Linux {}".format(self.release)
        else:
            return "{}, with Linux {}".format(self.os_name, self.release)

    @property
    def arch(self):
        kernel = Path(self.kernel)

        decomp = decompress(kernel)
        if decomp:
            head = decomp[:4096]
        else:
            with kernel.open("rb") as f:
                head = f.read(4096)

        if head[0x202:0x206] == b"HdrS":
            return Architecture("x86")
        elif head[0x38:0x3c] == b"ARM\x64":
            return Architecture("arm64")
        elif head[0x34:0x38] == b"\x45\x45\x45\x45":
            return Architecture("arm")

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
            "KernelEntry(release={!r}, kernel={!r}, initrd={!r}, fdtdir={!r}, os_name={!r})"
            .format(self.release, self.kernel, self.initrd, self.fdtdir, self.os_name)
        )


class Architecture(str):
    arm_32 = ["arm", "ARM", "armv7", "ARMv7", ]
    arm_64 = ["arm64", "ARM64", "aarch64", "AArch64"]
    arm = arm_32 + arm_64
    x86_32 = ["i386", "x86"]
    x86_64 = ["x86_64", "amd64", "AMD64"]
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

    @property
    def kernel_arches(self):
        if self in self.arm_32:
            return self.arm_32
        if self in self.arm_64:
            return self.arm
        if self in self.x86_32:
            return self.x86_32
        if self in self.x86_64:
            return self.x86
