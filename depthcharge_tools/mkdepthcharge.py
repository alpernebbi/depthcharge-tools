#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools mkdepthcharge program
# Copyright (C) 2020-2023 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import argparse
import logging
import os
import platform
import struct
import subprocess
import sys
import tempfile

from mmap import mmap
from pathlib import Path

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
)
from depthcharge_tools.utils.pathlib import (
    copy,
    decompress,
)
from depthcharge_tools.utils.platform import (
    Architecture,
    vboot_keys,
)
from depthcharge_tools.utils.string import (
    parse_bytesize,
)
from depthcharge_tools.utils.subprocess import (
    mkimage,
    vbutil_kernel,
    lz4,
    lzma,
    fdtget,
    fdtput,
)


class mkdepthcharge(
    Command,
    prog="mkdepthcharge",
    usage="%(prog)s [options] -o FILE [--] [VMLINUZ] [INITRAMFS ...] [DTB ...]",
    add_help=False,
):
    """Build boot images for the ChromeOS bootloader."""

    _logger = logging.getLogger(__name__)

    @property
    def logger(self):
        # Set verbosity before logging messages
        self.verbosity
        return self._logger

    # Inputs can have the same name and cause collisions in tmpdir.
    def _tempfile(self, name):
        f = self.tmpdir / name
        if not f.exists():
            return f

        for i in range(9999):
            f = f.with_name("{}-idx{:04}".format(name, i))
            if not f.exists():
                return f

        raise FileExistsError(self.tmpdir / name)

    # Debian packs the arm64 kernel uncompressed, but the bindeb-pkg
    # kernel target packs it as gzip. So we'll try to decompress inputs.
    def _decompress(self, f):
        self.logger.info(
            "Trying to decompress file '{}'."
            .format(f)
        )

        decomp = decompress(f, self._tempfile(f.name))
        if decomp is not None:
            self.logger.info(
                "Decompressed input '{}' as '{}'."
                .format(f, decomp)
            )

        return decomp or f

    # Copy inputs to tmpdir because mkimage wants modifiable files.
    def _copy(self, f):
        if self.tmpdir not in f.parents:
            f = copy(f, self._tempfile(f.name))
        f.chmod(0o755)

        return f

    @Group
    def input_files(self):
        """Input files"""

    @input_files.add
    @Argument(help=argparse.SUPPRESS)
    def files(self, *files):
        """Input files (vmlinuz, initramfs, dtbs)"""
        vmlinuz = []
        initramfs = []
        dtbs = []

        files = [Path(f).resolve() for f in files]

        for f in files:
            # Decompress files to run detection on content.
            decomp = self._decompress(f)
            with decomp.open("rb") as f_:
                head = f_.read(4096)

            # Portable Executable and ELF files
            if head.startswith(b"MZ") or head.startswith(b"ELF"):
                self.logger.info(
                    "File '{}' identified as a vmlinuz."
                    .format(f)
                )
                vmlinuz.append(decomp)

            # Cpio files
            elif (
                head.startswith(b"070701")
                or head.startswith(b"070702")
                or head.startswith(b"070707")
            ):
                self.logger.info(
                    "File '{}' identified as an initramfs."
                    .format(f)
                )
                # Keep initramfs compressed
                initramfs.append(f)

                # Avoid name collision when copying initramfs to tmpdir
                if decomp != f:
                    decomp.unlink()

            # Device-tree blobs
            elif head.startswith(b"\xd0\x0d\xfe\xed"):
                self.logger.info(
                    "File '{}' identified as a device-tree blob."
                    .format(f)
                )
                dtbs.append(decomp)

            # Failed to detect, assume in the order in usage string
            elif len(vmlinuz) == 0:
                self.logger.info(
                    "Assuming file '{}' is a vmlinuz."
                    .format(f)
                )
                vmlinuz.append(decomp)

            elif len(initramfs) == 0:
                self.logger.info(
                    "Assuming file '{}' is an initramfs."
                    .format(f)
                )
                # Keep initramfs compressed
                initramfs.append(f)

            else:
                self.logger.info(
                    "Assuming file '{}' is a device-tree blob."
                    .format(f)
                )
                dtbs.append(decomp)

        return {
            "vmlinuz": vmlinuz,
            "initramfs": initramfs,
            "dtbs": dtbs,
        }

    @input_files.add
    @Argument("-d", "--vmlinuz", nargs=1)
    def vmlinuz(self, vmlinuz=None):
        """Kernel executable"""
        files = self.files["vmlinuz"]

        if vmlinuz is not None:
            vmlinuz = Path(vmlinuz).resolve()
            self.logger.info(
                "Using file '{}' as a vmlinuz."
                .format(vmlinuz)
            )
            files = [self._decompress(vmlinuz), *files]

        if len(files) == 0:
            raise ValueError(
                "vmlinuz argument is required."
            )

        elif len(files) > 1:
            raise ValueError(
                "Can't build with multiple kernels"
            )

        vmlinuz = self._copy(files[0])

        return vmlinuz

    @input_files.add
    @Argument("-i", "--initramfs", metavar="INITRAMFS", nargs="+")
    def initramfs(self, *files):
        """Ramdisk images"""
        files = [
            *(Path(f).resolve() for f in files if f is not None),
            *self.files["initramfs"],
        ]

        for file in files:
            self.logger.info(
                "Using file '{}' as an initramfs."
                .format(file)
            )

        if len(files) > 1:
            self.logger.info(
                "Concatenating initramfs files as a single initramfs."
            )
            initramfs = self._tempfile("merged-initramfs.img")
            with initramfs.open('xb') as merge:
                for file in files:
                    merge.write(file.read_bytes())

        elif len(files) == 1:
            initramfs = self._copy(files[0])

        elif not files:
            initramfs = None

        return initramfs

    @input_files.add
    @Argument("-b", "--dtbs", metavar="DTB", nargs="+")
    def dtbs(self, *dtbs):
        """Device-tree binary file"""
        files = self.files["dtbs"]

        dtbs = [Path(dtb).resolve() for dtb in dtbs]
        for dtb in dtbs:
            self.logger.info(
                "Using file '{}' as a device-tree blob."
                .format(dtb)
            )

        dtbs = [self._decompress(dtb) for dtb in dtbs]
        dtbs = [self._copy(dtb) for dtb in (*dtbs, *files)]

        return dtbs

    @Group
    def options(self):
        """Options"""
        # Check incompatible combinations
        if self.image_format == "zimage":
            if self.compress not in (None, "none"):
                raise ValueError(
                    "Compress argument not supported with zimage format."
                )
            if self.name is not None:
                raise ValueError(
                    "Name argument not supported with zimage format."
                )
            if self.dtbs:
                raise ValueError(
                    "Device tree files not supported with zimage format."
                )

    @options.add
    @Argument("-h", "--help", action="help")
    def print_help(self):
        """Show this help message."""
        # type(self).parser.print_help()

    @options.add
    @Argument(
        "-V", "--version",
        action="version",
        version="depthcharge-tools %(prog)s {}".format(__version__),
    )
    def version(self):
        """Print program version."""
        return type(self).version.version % {"prog": type(self).prog}

    @options.add
    @Argument("-v", "--verbose", count=True)
    def verbosity(self, verbosity=0):
        """Print more detailed output."""
        level = logging.WARNING - int(verbosity) * 10
        self._logger.setLevel(level)
        return verbosity

    @options.add
    @Argument("-o", "--output", required=True)
    def output(self, file_):
        """Write resulting image to FILE."""

        # Output path is obviously required
        if file_ is None:
            raise ValueError(
                "Output argument is required."
            )

        return Path(file_).resolve()

    @options.add
    @Argument("--tmpdir", nargs=1)
    def tmpdir(self, dir_=None):
        """Directory to keep temporary files."""
        if dir_ is None:
            dir_ = tempfile.TemporaryDirectory(
                prefix="mkdepthcharge-",
            )
            dir_ = self.exitstack.enter_context(dir_)

        dir_ = Path(dir_)
        os.makedirs(dir_, exist_ok=True)

        self.logger.debug("Working in temp dir '{}'.".format(dir_))

        return dir_

    @options.add
    @Argument("-A", "--arch", nargs=1)
    def arch(self, arch=None):
        """Architecture to build for."""

        # We should be able to make an image for other architectures, but
        # the default should be whatever board the kernel is for.
        if arch is None:
            with self.vmlinuz.open("rb") as f:
                head = f.read(4096)

            if head[0x202:0x206] == b"HdrS":
                arch = Architecture("x86")
            elif head[0x38:0x3c] == b"ARM\x64":
                arch = Architecture("arm64")
            elif head[0x34:0x38] == b"\x45\x45\x45\x45":
                arch = Architecture("arm")

            self.logger.info(
                "Assuming CPU architecture '{}' from vmlinuz file."
                .format(arch)
            )

        elif arch not in Architecture.all:
            raise ValueError(
                "Can't build images for unknown architecture '{}'"
                .format(arch)
            )

        return Architecture(arch)

    @options.add
    @Argument("--format", nargs=1)
    def image_format(self, format_=None):
        """Kernel image format to use."""

        # Default to architecture-specific formats.
        if format_ is None:
            if self.arch in Architecture.arm:
                format_ = "fit"
            elif self.arch in Architecture.x86:
                format_ = "zimage"
            self.logger.info("Assuming image format '{}'.".format(format_))

        if format_ not in ("fit", "zimage"):
            raise ValueError(
                "Can't build images for unknown image format '{}'"
                .format(format_)
            )

        return format_

    @options.add
    @Argument("--kernel-start", nargs=1)
    def kernel_start(self, addr=None):
        """Start of depthcharge kernel buffer in memory."""
        if addr is not None:
            return parse_bytesize(addr)

        if self.arch in Architecture.x86:
            return 0x100000

    @options.add
    @Argument(
        "--no-pad-vmlinuz", pad=False,
        help=argparse.SUPPRESS,
    )
    @Argument(
        "--pad-vmlinuz", pad=True,
        help="Pad vmlinuz for safe decompression.",
    )
    def pad_vmlinuz(self, pad=None):
        """Pad vmlinuz for safe decompression."""
        if pad is None:
            pad = (
                self.image_format == "fit"
                and self.patch_dtbs
            )

        return bool(pad)

    @Group
    def fit_options(self):
        """FIT image options"""

    @fit_options.add
    @Argument("-C", "--compress", nargs=1)
    def compress(self, type_=None):
        """Compress vmlinuz file before packing."""

        # We need to pass "-C none" to mkimage or it assumes gzip.
        if type_ is None and self.image_format == "fit":
            type_ = "none"

        if type_ not in (None, "none", "lz4", "lzma"):
            raise ValueError(
                "Compression type '{}' is not supported."
                .format(type_)
            )

        return type_

    @fit_options.add
    @Argument("-n", "--name", nargs=1)
    def name(self, desc=None):
        """Description of vmlinuz to put in the FIT."""

        # If we don't pass "-n <name>" to mkimage, the kernel image
        # description is left blank. Other images get "unavailable"
        # as their description, so it looks better if we match that.
        if desc is None and self.image_format == "fit":
            desc = "unavailable"

        return desc

    @fit_options.add
    @Argument("--ramdisk-load-address", nargs=1)
    def ramdisk_load_address(self, addr=None):
        """Add load address to FIT ramdisk image section."""
        if addr is not None:
            return parse_bytesize(addr)

        return None

    @fit_options.add
    @Argument(
        "--no-patch-dtbs", patch_dtbs=False,
        help=argparse.SUPPRESS,
    )
    @Argument(
        "--patch-dtbs", patch_dtbs=True,
        help="Add linux,initrd properties to device-tree binary files.",
    )
    def patch_dtbs(self, patch_dtbs=False):
        """Add linux,initrd properties to device-tree binary files."""
        if (
            patch_dtbs
            and self.kernel_start is None
            and self.ramdisk_load_address is None
        ):
            raise ValueError(
                "The kernel buffer start address or a ramdisk load address "
                "is required to patch DTB files for initramfs support."
            )

        return bool(patch_dtbs)

    @Group
    def zimage_options(self):
        """zImage format options"""

    @zimage_options.add
    @Argument(
        "--no-set-init-size", init_size=False,
        help="Don't set init_size boot param.",
    )
    @Argument(
        "--set-init-size", init_size=True,
        help=argparse.SUPPRESS,
    )
    def set_init_size(self, init_size=None):
        """Set init_size boot param for safe decompression."""
        if init_size is None:
            return (
                self.image_format == "zimage"
                and self.initramfs is not None
            )

        return bool(init_size)

    @Group
    def vboot_options(self):
        """Depthcharge image options"""

        keydirs = []
        if self.keydir is not None:
            keydirs += [self.keydir]

        # If any of the arguments are given, search nearby for others
        if self.keyblock is not None:
            keydirs += [self.keyblock.parent]
        if self.signprivate is not None:
            keydirs += [self.signprivate.parent]
        if self.signpubkey is not None:
            keydirs += [self.signpubkey.parent]

        if None in (self.keyblock, self.signprivate, self.signpubkey):
            for d in sorted(set(keydirs), key=keydirs.index):
                self.logger.info(
                    "Searching '{}' for vboot keys."
                    .format(d)
                )

            # Defaults to distro-specific paths for necessary files.
            keydir, keyblock, signprivate, signpubkey = vboot_keys(*keydirs)

            if keydir:
                self.logger.info(
                    "Defaulting to keys from '{}' for missing arguments."
                    .format(keydir)
                )

            if self.keyblock is None:
                self.keyblock = keyblock
            if self.signprivate is None:
                self.signprivate = signprivate
            if self.signpubkey is None:
                self.signpubkey = signpubkey

        # We might still not have the vboot keys after all that.
        if self.keyblock is None:
            raise ValueError(
                "Couldn't find a usable keyblock file."
            )
        elif not self.keyblock.is_file():
            raise ValueError(
                "Keyblock file '{}' does not exist."
                .format(self.keyblock)
            )
        else:
            self.logger.info(
                "Using keyblock file '{}'."
                .format(self.keyblock)
            )

        if self.signprivate is None:
            raise ValueError(
                "Couldn't find a usable signprivate file."
            )
        elif not self.signprivate.is_file():
            raise ValueError(
                "Signprivate file '{}' does not exist."
                .format(self.signprivate)
            )
        else:
            self.logger.info(
                "Using signprivate file '{}'."
                .format(self.signprivate)
            )

        if self.signpubkey is None:
            self.logger.warning(
                "Couldn't find a usable signpubkey file."
            )
        elif not self.signpubkey.is_file():
            self.logger.warning(
                "Signpubkey file '{}' does not exist."
                .format(self.keyblock)
            )
            self.signpubkey = None
        else:
            self.logger.info(
                "Using signpubkey file '{}'."
                .format(self.signpubkey)
            )

    @vboot_options.add
    @Argument("-c", "--cmdline", append=True, nargs="+")
    def cmdline(self, *cmd):
        """Command-line parameters for the kernel."""

        # If the cmdline is empty vbutil_kernel returns an error. We can use
        # "--" instead of putting a newline or a space into the cmdline.
        if len(cmd) == 0:
            cmdline = "--"
        elif len(cmd) == 1 and isinstance(cmd[0], str):
            cmdline = cmd[0]
        elif isinstance(cmd, (list, tuple)):
            cmdline = " ".join(cmd)

        # The firmware replaces any '%U' in the kernel cmdline with the
        # PARTUUID of the partition it booted from. Chrome OS uses
        # kern_guid=%U in their cmdline and it's useful information, so
        # prepend it to cmdline.
        if (self.kern_guid is None) or self.kern_guid:
            cmdline = " ".join(("kern_guid=%U", cmdline))

        return cmdline

    @vboot_options.add
    @Argument(
        "--no-kern-guid", kern_guid=False,
        help="Don't prepend kern_guid=%%U to the cmdline."
    )
    @Argument(
        "--kern-guid", kern_guid=True,
        help=argparse.SUPPRESS,
    )
    def kern_guid(self, kern_guid=True):
        """Prepend kern_guid=%%U to the cmdline."""
        return kern_guid

    @vboot_options.add
    @Argument("--bootloader", nargs=1)
    def bootloader(self, file_=None):
        """Bootloader stub binary to use."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        if (
            self.image_format == "zimage"
            and self.initramfs is not None
            and file_ is not None
        ):
            raise ValueError(
                "Can't build images with both initramfs and "
                "bootloader stub for zimage format."
            )

        return file_

    @vboot_options.add
    @Argument("--keydir")
    def keydir(self, dir_):
        """Directory containing vboot keys to use."""
        if dir_ is not None:
            dir_ = Path(dir_).resolve()

        return dir_

    @vboot_options.add
    @Argument("--keyblock")
    def keyblock(self, file_):
        """The key block file (.keyblock)."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        return file_

    @vboot_options.add
    @Argument("--signprivate")
    def signprivate(self, file_):
        """Private key (.vbprivk) to sign the image."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        return file_

    @vboot_options.add
    @Argument("--signpubkey")
    def signpubkey(self, file_):
        """Public key (.vbpubk) to verify the image."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        return file_

    def __call__(self):
        vmlinuz = self.vmlinuz
        initramfs = self.initramfs
        bootloader = self.bootloader
        dtbs = self.dtbs
        tmpdir = self.tmpdir

        if bootloader is not None:
            bootloader = copy(bootloader, tmpdir)

        # Depthcharge on arm64 with FIT supports these two compressions.
        if self.compress == "lz4":
            self.logger.info("Compressing kernel with lz4.")
            vmlinuz = lz4.compress(vmlinuz, self._tempfile("vmlinuz.lz4"))
        elif self.compress == "lzma":
            self.logger.info("Compressing kernel with lzma.")
            vmlinuz = lzma.compress(vmlinuz, self._tempfile("vmlinuz.lzma"))
        elif self.compress not in (None, "none"):
            fmt = "Compression type '{}' is not supported."
            msg = fmt.format(compress)
            raise ValueError(msg)

        # vbutil_kernel --config argument wants cmdline as a file.
        cmdline_file = self._tempfile("kernel.args")
        cmdline_file.write_text(self.cmdline)

        # vbutil_kernel --bootloader argument is mandatory, but it's
        # unused in depthcharge except as a multiboot ramdisk. Prepare
        # this empty file as its replacement where necessary.
        empty = self._tempfile("empty.bin")
        empty.write_bytes(bytes(512))

        # The kernel decompression overwrites parts of the buffer we
        # control while decompressing itself. We need to make sure we
        # don't place initramfs in that range. For that, we need to know
        # how offsets in file correspond to addresses in memory.

        def addr_to_offs(addr, load_addr=self.kernel_start):
            return addr - load_addr + 0x10000

        def offs_to_addr(offs, load_addr=self.kernel_start):
            return offs + load_addr - 0x10000

        def align_up(size, align=0x1000):
            return ((size + align - 1) // align) * align

        # Size for a small padding, sometimes necessary in some
        # places for unknown reasons, added and set empirically.
        small_pad = 0x40000

        if self.image_format == "fit":
            fit_image = self._tempfile("depthcharge.fit")

            initramfs_args = []
            if initramfs is not None:
                initramfs_args += ["-i", initramfs]

            dtb_args = []
            for dtb in dtbs:
                dtb_args += ["-b", dtb]

            # The subimage nodes can be <type>@1 or <type>-1.
            def subimage_by_type(fit_image, subimage_type):
                for subimage in fdtget.subnodes(fit_image, "/images"):
                    node = "/images/{}".format(subimage)
                    try:
                        if fdtget.get(fit_image, node, "type") == subimage_type:
                            return node
                    except:
                        continue

            # On later 32-bit ARM Chromebooks, the KERNEL_START address
            # can be very close to the where kernel decompresses itself
            # that the process overwrites the initramfs. The device-tree
            # is luckily copied away before then. We need to add some
            # vmlinuz padding to prevent this.
            if initramfs is not None and self.pad_vmlinuz:

                # We need the decompressed kernel size, not easy to get.
                # Try to find the compressed vmlinux inside vmlinuz,
                # then try to decompress it.
                data = vmlinuz.read_bytes()
                vmlinuz_size = len(data)
                decomp_size = -1

                for fmt, magic in {
                    "gzip":  b'\x1f\x8b\x08',
                    "xz":    b'\xfd7zXZ\x00',
                    "zstd":  b'(\xb5/\xfd',
                    "lzma":  b'\x5d\x00\x00\x00',
                    "lz4":   b'\02!L\x18',
                    "bzip2": b'BZh',
                    "lzop":  b'\x89\x4c\x5a',
                }.items():
                    offs = data.find(magic)
                    while 0 < offs < vmlinuz_size:
                        decomp = decompress(data[offs:], partial=True)
                        if decomp:
                            self.logger.info(
                                "Found {} at {:#x} in vmlinuz, with size {:#x}."
                                .format(fmt, offs, len(decomp))
                            )
                            decomp_size = max(decomp_size, len(decomp))
                        offs = data.find(magic, offs + 1)

                if decomp_size == -1:
                    raise ValueError(
                        "Couldn't find decompressed kernel inside vmlinuz."
                    )

                self.logger.info(
                    "Vmlinuz size is {:#x}, {:#x} decompressed."
                    .format(vmlinuz_size, decomp_size)
                )

                # Decompression starts at start of physical memory,
                # calculated per AUTO_ZRELADDR. But first kernel copies
                # itself after where the decompressed copy would end.
                decomp_addr = self.kernel_start & 0xf8000000
                safe_initrd_start = (
                    decomp_addr + decomp_size + vmlinuz_size + small_pad
                )
                initrd_start = (
                    self.kernel_start + vmlinuz_size
                    + sum(dtb.stat().st_size for dtb in self.dtbs)
                )

                if initrd_start < safe_initrd_start:
                    pad_to = align_up(
                        vmlinuz_size
                        + (safe_initrd_start - initrd_start)
                    )
                    self.logger.info(
                        "Padding vmlinuz to {:#x}."
                        .format(pad_to)
                    )
                    with vmlinuz.open("r+b") as f, mmap(f.fileno(), 0) as data:
                        data.resize(pad_to)

            # The later 32-bit ARM Chromebooks use Depthcharge, but
            # their stock versions don't have the code to support FIT
            # ramdisks. But since we know the fixed KERNEL_START we can
            # deduce where the initramfs will be, and inject its address
            # into the DTBs the way Linux expects bootloaders to do.
            if initramfs is not None and self.patch_dtbs:

                # We'll probably never need this, as only old U-Boot builds
                # need a ramdisk load address and those can handle the
                # initrd properties fine.
                if self.ramdisk_load_address:
                    initrd_start = self.ramdisk_load_address
                    initrd_end = initrd_start + initramfs.stat().st_size

                else:
                    # Allocate space for the properties we want to set,
                    # adding them later would shift things around.
                    self.logger.info("Preparing dtb files for initramfs support.")
                    for dtb in dtbs:
                        fdtput.put(dtb, "/chosen", "linux,initrd-start", 0)
                        fdtput.put(dtb, "/chosen", "linux,initrd-end", 0)

                    # Make a temporary image and search for the initramfs
                    # inside it, because I don't want to risk a wrong
                    # estimate and don't want to mess with pylibfdt.
                    self.logger.info("Packing files as temp FIT image:")
                    tmp_image = self._tempfile("depthcharge.fit.tmp")
                    proc = mkimage(
                        "-f", "auto",
                        "-A", self.arch.mkimage,
                        "-T", "kernel",
                        "-O", "linux",
                        "-C", self.compress,
                        "-n", self.name,
                        *initramfs_args,
                        *dtb_args,
                        "-d", vmlinuz,
                        tmp_image,
                    )
                    self.logger.info(proc.stdout)

                    # Mkimage breaks the config node key with -T kernel_noload.
                    # Apparently this shifts things around as well, so...
                    self.logger.info("Patching temp FIT for kernel_noload type.")
                    fdtput.put(
                        tmp_image, subimage_by_type(tmp_image, "kernel"),
                        "type", "kernel_noload",
                    )

                    with tmp_image.open("r+b") as f, mmap(f.fileno(), 0) as data:
                        initrd_offset = data.find(initramfs.read_bytes())
                        self.logger.info(
                            "Initramfs is at offset {:#x} in FIT image."
                            .format(initrd_offset)
                        )
                    initrd_start = initrd_offset + self.kernel_start
                    initrd_end = initrd_start + initramfs.stat().st_size

                self.logger.info(
                    "Initramfs should be at address {:#x} - {:#x} in memory."
                    .format(initrd_start, initrd_end)
                )

                self.logger.info("Patching dtb files for initramfs support.")
                for dtb in dtbs:
                    fdtput.put(dtb, "/chosen", "linux,initrd-start", initrd_start)
                    fdtput.put(dtb, "/chosen", "linux,initrd-end", initrd_end)

            self.logger.info("Packing files as FIT image:")
            proc = mkimage(
                "-f", "auto",
                "-A", self.arch.mkimage,
                "-T", "kernel",
                "-O", "linux",
                "-C", self.compress,
                "-n", self.name,
                *initramfs_args,
                *dtb_args,
                "-d", vmlinuz,
                fit_image,
            )
            self.logger.info(proc.stdout)

            # Earlier 32-bit ARM Chromebooks use U-Boot, which needs a
            # usable load address for the FIT ramdisk image section.
            if initramfs is not None and self.ramdisk_load_address:
                self.logger.info("Patching FIT for ramdisk load address.")
                fdtput.put(
                    fit_image, subimage_by_type(fit_image, "ramdisk"),
                    "load", self.ramdisk_load_address,
                )

            # Mkimage breaks the config node key with -T kernel_noload.
            self.logger.info("Patching FIT for kernel_noload type.")
            fdtput.put(
                fit_image, subimage_by_type(fit_image, "kernel"),
                "type", "kernel_noload",
            )

            if (
                initramfs is not None
                and self.patch_dtbs
                and self.ramdisk_load_address is None
            ):
                with fit_image.open("r+b") as f, mmap(f.fileno(), 0) as data:
                    if initrd_offset != data.find(initramfs.read_bytes()):
                        raise RuntimeError(
                            "Initramfs FIT offset changed after rebuild."
                        )

            self.logger.info("Packing files as depthcharge image.")
            proc = vbutil_kernel(
                "--version", "1",
                "--arch", self.arch.vboot,
                "--vmlinuz", fit_image,
                "--config", cmdline_file,
                "--bootloader", bootloader or empty,
                "--keyblock", self.keyblock,
                "--signprivate", self.signprivate,
                "--pack", self.output,
            )
            self.logger.info(proc.stdout)

        elif self.image_format == "zimage" and initramfs is None:
            self.logger.info("Packing files as depthcharge image.")
            proc = vbutil_kernel(
                "--version", "1",
                "--arch", self.arch.vboot,
                "--vmlinuz", vmlinuz,
                "--config", cmdline_file,
                "--bootloader", bootloader or empty,
                "--keyblock", self.keyblock,
                "--signprivate", self.signprivate,
                "--pack", self.output,
            )
            self.logger.info(proc.stdout)

        elif self.image_format == "zimage":
            # bzImage header has the address the kernel will decompress
            # to, and the amount of memory it needs there to work.
            # See Documentation/x86/boot.rst in Linux tree for offsets.
            with vmlinuz.open("r+b") as f, mmap(f.fileno(), 0) as data:
                if data[0x202:0x206] != b"HdrS":
                    raise ValueError(
                        "Vmlinuz file is not a Linux kernel bzImage."
                    )

                pref_address, init_size = struct.unpack(
                    "<QI", data[0x258:0x264]
                )
                self.logger.info(
                    "Vmlinuz pref_address is {:#x}, with init_size {:#x}."
                    .format(pref_address, init_size)
                )

                # Initramfs gets corrupted if it's too close to vmlinuz
                pad_to = align_up(data.size()) + small_pad

                # KASLR takes care to avoid overwriting initramfs in
                # self-decompression, but if that's disabled we need to
                # put the initramfs outside the decompression buffer.
                # But if the kernel and initramfs are small enough, they
                # might fit before pref_address, where we can skip that.
                low_usable = pref_address - align_up(data.size()) - small_pad
                if self.pad_vmlinuz and initramfs.stat().st_size > low_usable:
                    pad_to = align_up(addr_to_offs(pref_address + init_size))

                if pad_to > data.size():
                    self.logger.info(
                        "Padding vmlinuz to size {:#x}"
                        .format(pad_to)
                    )
                    data.resize(pad_to)

            # vbutil_kernel picks apart the vmlinuz in ways I don't
            # really want to reimplement right now, so just call it.
            self.logger.info("Packing files as temporary image.")
            temp_img = self._tempfile("temp.img")
            proc = vbutil_kernel(
                "--version", "1",
                "--arch", self.arch.vboot,
                "--vmlinuz", vmlinuz,
                "--config", cmdline_file,
                "--bootloader", initramfs,
                "--keyblock", self.keyblock,
                "--signprivate", self.signprivate,
                "--pack", temp_img,
            )
            self.logger.info(proc.stdout)

            # Do binary editing for now, until I get time to write
            # parsers for vboot_reference structs and kernel headers.
            with temp_img.open("r+b") as f, mmap(f.fileno(), 0) as data:
                if data[:8] != b"CHROMEOS":
                    raise RuntimeError(
                        "Unexpected output format from vbutil_kernel, "
                        "expected 'CHROMEOS' magic at start of file."
                    )

                # File starts with a keyblock and a kernel preamble
                # immediately afterwards, and padding up to 0x10000.
                keyblock_size = struct.unpack(
                    "<I", data[0x10:0x14]
                )[0]
                p = preamble_offset = keyblock_size

                # Preamble has the "memory address" of the "bootloader"
                # but it assumes the body is loaded at 0x100000.
                bootloader_addr = struct.unpack(
                    "<I", data[p+0x38:p+0x3c]
                )[0]
                bootloader_offset = addr_to_offs(bootloader_addr, 0x100000)

                # Assume vbutil_kernel correctly put it as "bootloader"
                initramfs_offset = bootloader_offset
                initramfs_addr = offs_to_addr(initramfs_offset)
                initramfs_size = initramfs.stat().st_size

                self.logger.info(
                    "Initramfs is at offset {:#x}, address {:#x}, size {:#x}."
                    .format(initramfs_offset, initramfs_addr, initramfs_size)
                )

                # Params is immediately before bootloader with size 0x1000
                p = params_offset = bootloader_offset - 0x1000
                if data[p+0x202:p+0x206] != b"HdrS":
                    raise RuntimeError(
                        "Unexpected output format from vbutil_kernel, "
                        "expected 'HdrS' magic in boot params."
                    )

                # These get passed to the kernel unmodified by depthcharge.
                # "initrdmem=addr,size" in the cmdline would work, but
                # this looks like how bootloaders are supposed to do it.
                data[p+0x218:p+0x21c] = struct.pack("<I", initramfs_addr)
                data[p+0x21c:p+0x220] = struct.pack("<I", initramfs_size)

                # Kernel self-decompression first copies vmlinuz to avoid
                # overwriting itself, ending at pref_address + init_size
                # or so. Increasing init_size in the boot params makes
                # it avoid overwriting our initramfs. Also needs some
                # small padding for unknown reasons.
                if self.set_init_size:
                    safe_copy_end = align_up(
                        initramfs_addr + initramfs_size
                        + small_pad
                        + vmlinuz.stat().st_size
                    )
                    if pref_address + init_size < safe_copy_end:
                        init_size = safe_copy_end - pref_address
                        self.logger.info(
                            "Setting init_size = {:#x}."
                            .format(init_size)
                        )
                        data[p+0x260:p+0x264] = struct.pack("<I", init_size)

            self.logger.info("Re-signing edited temporary image.")
            proc = vbutil_kernel(
                "--keyblock", self.keyblock,
                "--signprivate", self.signprivate,
                "--oldblob", temp_img,
                "--repack", self.output,
            )
            self.logger.info(proc.stdout)

        self.logger.info("Verifying built depthcharge image:")
        signpubkey_args = []
        if self.signpubkey is not None:
            signpubkey_args += ["--signpubkey", self.signpubkey]

        proc = vbutil_kernel(
            "--verify", self.output,
            *signpubkey_args,
        )
        self.logger.info(proc.stdout)

        return self.output


if __name__ == "__main__":
    mkdepthcharge.main()
