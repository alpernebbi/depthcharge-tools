#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl build subcommand
# Copyright (C) 2020-2023 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import argparse
import collections
import configparser
import logging
import os
import shlex
import textwrap

from pathlib import Path
from functools import lru_cache

from depthcharge_tools import __version__
from depthcharge_tools.mkdepthcharge import mkdepthcharge
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
    CommandExit,
)
from depthcharge_tools.utils.os import (
    Partition,
)
from depthcharge_tools.utils.pathlib import (
    copy,
)
from depthcharge_tools.utils.platform import (
    KernelEntry,
    cpu_microcode,
    vboot_keys,
    installed_kernels,
    root_requires_initramfs,
)
from depthcharge_tools.utils.subprocess import (
    fdtget,
)

from depthcharge_tools.depthchargectl import depthchargectl


class SizeTooBigError(CommandExit):
    def __init__(self):
        super().__init__(
            "Couldn't build a small enough image for this board.",
            returncode=4,
        )


class InitramfsSizeTooBigError(SizeTooBigError):
    def __init__(self):
        super(SizeTooBigError, self).__init__(
            "Couldn't build a small enough image for this board. "
            "This is usually solvable by making the initramfs smaller, "
            "check your OS's documentation on how to do so.",
            returncode=3,
        )


@depthchargectl.subcommand("build")
class depthchargectl_build(
    depthchargectl,
    prog="depthchargectl build",
    usage="%(prog)s [options] [KERNEL_VERSION]",
    add_help=False,
):
    """Buld a depthcharge image for the running system."""

    _logger = depthchargectl._logger.getChild("build")
    config_section = "depthchargectl/build"

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument
    def kernel_version(self, kernel_version=None):
        """Installed kernel version to build an image for."""
        if isinstance(kernel_version, KernelEntry):
            return kernel_version

        kernels = installed_kernels(
            root=self.root_mountpoint,
            boot=self.boot_mountpoint,
        )

        kernel_arches = self.board.arch.kernel_arches
        for k in list(kernels):
            if k.arch not in kernel_arches:
                self.logger.info(
                    "Ignoring kernel '{}' incompatible with board arch."
                    .format(k.release or "(unknown)")
                )
                kernels.remove(k)

        if isinstance(kernel_version, str):
            kernel = max(
                (k for k in kernels if k.release == kernel_version),
                default=None,
            )

            if kernel is None:
                raise ValueError(
                    "Could not find an installed kernel for version '{}'."
                    .format(kernel_version)
                )

        elif kernels:
            kernel = max(kernels)

        else:
            self.logger.warning(
                "Could not find any installed kernel."
            )
            kernel = None

        return kernel

    @Group
    def options(self):
        """Options"""

    @depthchargectl.board.copy()
    def board(self, codename=""):
        board = super().board

        if board is None:
            raise ValueError(
                "Cannot build depthcharge images when no board is specified.",
            )

        return board

    @depthchargectl.zimage_initramfs_hack.copy()
    def zimage_initramfs_hack(self, hack=None):
        hack = super().zimage_initramfs_hack

        if hack not in (None, "set-init-size", "pad-vmlinuz"):
            raise ValueError(
                "Unknown zimage initramfs support hack '{}'."
                .format(hack)
            )

        return hack

    @Group
    def custom_kernel_options(self):
        """Custom kernel specification"""

    @custom_kernel_options.add
    @Argument("--kernel-release", nargs=1)
    def kernel_release(self, name=None):
        """Release name for the kernel used in image name"""
        if name is None and self.kernel_version is not None:
            if self.kernel == self.kernel_version.kernel:
                name = self.kernel_version.release

        return name

    @custom_kernel_options.add
    @Argument("--kernel", nargs=1)
    def kernel(self, file_=None):
        """Kernel executable"""
        if file_ is None and self.kernel_version is not None:
            file_ = self.kernel_version.kernel

        # vmlinuz is always mandatory
        if file_ is None and self.kernel_release is not None:
            raise ValueError(
                "No vmlinuz file found for version '{}'."
                .format(self.kernel_release)
            )

        elif file_ is None:
            raise ValueError("No vmlinuz file found.")

        return Path(file_)

    @custom_kernel_options.add
    @Argument("--initramfs", nargs='+')
    def initrd(self, *files):
        """Ramdisk images"""
        # Trigger more important errors first
        self.kernel

        if not files and self.kernel_version is not None:
            if self.kernel == self.kernel_version.kernel:
                microcode = cpu_microcode(self.boot_mountpoint)
                files = [*microcode, self.kernel_version.initrd]

        if self.ignore_initramfs:
            for file in files:
                self.logger.warning(
                    "Ignoring initramfs '{}' as configured."
                    .format(file)
                )
            return None

        if len(files) == 1 and files[0] in (None, "None", "none"):
            self.logger.warning("Not using initramfs.")
            return None

        # Initramfs is optional.
        if not files and self.kernel_release is not None:
            self.logger.info(
                "No initramfs file found for version '{}'."
                .format(self.kernel_release)
            )
            return None

        elif not files:
            self.logger.info("No initramfs file found.")
            return None

        else:
            return [Path(file) for file in files]

    @custom_kernel_options.add
    @Argument("--fdtdir", nargs=1)
    def fdtdir(self, dir_=None):
        """Directory to search device-tree binaries for the board"""
        if dir_ is None and self.kernel_version is not None:
            if self.kernel == self.kernel_version.kernel:
                dir_ = self.kernel_version.fdtdir

        if dir_ is None:
            return None
        else:
            return Path(dir_)

    @custom_kernel_options.add
    @Argument("--dtbs", nargs="+", metavar="FILE")
    def dtbs(self, *files):
        """Device-tree binary files to use instead of searching fdtdir"""
        # Trigger more important errors first
        self.kernel

        # Device trees are optional based on board configuration.
        if self.board.dt_compatible and len(files) == 0:
            if self.fdtdir is None and self.kernel_release is not None:
                raise ValueError(
                    "No dtb directory found for version '{}', "
                    "but this board needs a dtb."
                    .format(self.kernel_release)
                )

            elif self.fdtdir is None:
                raise ValueError(
                    "No dtb directory found, "
                    "but this board needs a dtb."
                )

            self.logger.info(
                "Searching '{}' for dtbs compatible with pattern '{}'."
                .format(self.fdtdir, self.board.dt_compatible.pattern)
            )

            def is_compatible(dt_file):
                return any(
                    self.board.dt_compatible.fullmatch(compat)
                    for compat in fdtget.get(
                        dt_file, "/", "compatible", default="",
                    ).split()
                )

            files = list(filter(
                is_compatible,
                self.fdtdir.glob("**/*.dtb"),
            ))

            if len(files) == 0:
                raise ValueError(
                    "No dtb file compatible with pattern '{}' found in '{}'."
                    .format(self.board.dt_compatible.pattern, self.fdtdir)
                )

        else:
            files = [Path(f) for f in files]

        if self.board.image_format == "zimage" and len(files) != 0:
            raise ValueError(
                "Image format '{}' doesn't support dtb files."
                .format(self.board.image_format)
            )

        return sorted(files, key=lambda f: f.name)

    @options.add
    @Argument("--description", nargs=1)
    def description(self, desc=None):
        """Human-readable description for the image"""
        if desc is None and self.kernel_version is not None:
            desc = self.kernel_version.description

        return desc

    @options.add
    @depthchargectl.root.copy("--root")
    def root(self, root=None):
        """Root device to add to the kernel cmdline"""
        if root in ("", "None", "none"):
            return None

        root = super().root

        if isinstance(root, Path):
            mnt = self.root_mountpoint
            root = self.diskinfo.by_mountpoint("/", fstab_only=True)

            if root:
                self.logger.info(
                    "Using root '{}' set in '{}'."
                    .format(root, mnt / "etc" / "fstab")
                )
                return root

            dev = self.diskinfo.by_mountpoint(mnt)
            uuid = self.diskinfo.get_uuid(dev)
            if uuid:
                root = "UUID={}".format(uuid.upper())
                self.logger.warning(
                    "Using '{}' as root from currently mounted '{}'."
                    .format(root, dev)
                )
                return root

            if mnt != Path("/").resolve():
                raise ValueError(
                    "Couldn't convert mountpoint '{}' to a root cmdline."
                    .format(mnt)
                )

            raise ValueError(
                "Couldn't figure out a root cmdline for this system."
                .format(mnt)
            )

        if not self.diskinfo.evaluate(root):
            self.logger.warning(
                "Using root '{}' but it's not a device or mountpoint."
                .format(root)
            )

        return str(root)

    @depthchargectl.kernel_cmdline.copy()
    def kernel_cmdline(self, *cmds):
        # This is some deep magic that evaluates self.kernel_cmdline
        # according to the parent definition and sets it in self.
        cmdline = super().kernel_cmdline

        # This evaluates self.root with the above self.kernel_cmdline,
        # then continues here to set self.kernel_cmdline a second time.
        append_root = self.root is not None

        for c in list(cmdline):
            lhs, _, rhs = c.partition("=")
            if lhs.lower() != "root":
                continue

            if rhs == self.root:
                append_root = False
                continue

            if self.root is None:
                self.logger.warning(
                    "Kernel cmdline has a root '{}', keeping it."
                    .format(rhs)
                )
                continue

            self.logger.warning(
                "Kernel cmdline has a different root '{}', removing it."
                .format(rhs)
            )
            cmdline.remove(c)

        if append_root:
            self.logger.info(
                "Appending 'root={}' to kernel cmdline."
                .format(self.root)
            )
            cmdline.append('root={}'.format(self.root))

        if self.ignore_initramfs:
            self.logger.warning(
                "Ignoring initramfs as configured, "
                "appending 'noinitrd' to the kernel cmdline."
                .format(self.initrd)
            )
            cmdline.append("noinitrd")

        # Linux kernel without an initramfs only supports certain
        # types of root parameters, check for them.
        if self.initrd is None and self.root is not None:
            if root_requires_initramfs(self.root):
                raise ValueError(
                    "An initramfs is required for root '{}'."
                    .format(self.root)
                )

        return cmdline

    @options.add
    @Argument("--compress", nargs="+", metavar="TYPE")
    def compress(self, *compress):
        """Compression types to attempt."""

        # Allowed compression levels. We will call mkdepthcharge by
        # hand multiple times for these.
        for c in compress:
            if c not in ("none", "lz4", "lzma"):
                raise ValueError(
                    "Unsupported compression type '{}'."
                    .format(t)
                )

        if len(compress) == 0:
            compress = ["none"]
            if self.board.boots_lz4_kernel:
                compress += ["lz4"]
            if self.board.boots_lzma_kernel:
                compress += ["lzma"]

            # zimage doesn't support compression
            if self.board.image_format == "zimage":
                compress = ["none"]

        return sorted(set(compress), key=compress.index)

    @options.add
    @Argument("--timestamp", nargs=1)
    def timestamp(self, seconds=None):
        """Build timestamp for the image"""
        if seconds is None:
            if "SOURCE_DATE_EPOCH" in os.environ:
                seconds = os.environ["SOURCE_DATE_EPOCH"]

        # Initramfs date is bound to be later than vmlinuz date, so
        # prefer that if possible.
        if seconds is None:
            if self.initrd is not None:
                seconds = max(
                    int(initrd.stat().st_mtime)
                    for initrd in self.initrd
                )
            else:
                seconds = int(self.kernel.stat().st_mtime)

        if seconds is None:
            self.logger.error(
                "Couldn't determine a timestamp from initramfs "
                "nor vmlinuz."
            )

        return seconds

    @options.add
    @Argument("-o", "--output", nargs=1)
    def output(self, path=None):
        """Output image to path instead of storing in images-dir"""
        if path is None:
            image_name = "{}.img".format(self.kernel_release or "default")
            path = self.images_dir / image_name

        return Path(path)

    def __call__(self):
        self.logger.warning(
            "Building depthcharge image for board '{}' ('{}')."
            .format(self.board.name, self.board.codename)
        )

        self.logger.info(
            "Building for kernel version '{}'."
            .format(self.kernel_release or "(unknown)")
        )

        # Images dir might not have been created at install-time
        os.makedirs(self.output.parent, exist_ok=True)

        # Build to a temporary file so we do not overwrite existing
        # images with an unbootable image.
        outtmp = self.tmpdir / "{}.tmp".format(self.output.name)

        # Try to keep output reproducible.
        if self.timestamp is not None:
            os.environ["SOURCE_DATE_EPOCH"] = str(self.timestamp)

        # Error early if initramfs is absolutely too big to fit
        initrd_size = (
            sum(initrd.stat().st_size for initrd in self.initrd)
            if self.initrd is not None
            else 0
        )
        if initrd_size >= self.board.image_max_size:
            self.logger.error(
                "Initramfs alone is larger than the maximum image size."
            )
            raise InitramfsSizeTooBigError()

        # The earliest boards apparently have an off-by-one error while
        # loading the chosen dtb, adding each file twice solves it.
        dtbs = (
            self.dtbs
            if not self.board.loads_dtb_off_by_one else
            [dtb for dtb in self.dtbs for _ in (0, 1)]
        )

        # Skip compress="none" if inputs wouldn't fit max image size
        compress_list = self.compress
        inputs_size = sum([
            self.kernel.stat().st_size,
            initrd_size,
            *(dtb.stat().st_size for dtb in dtbs),
        ])

        if inputs_size > self.board.image_max_size and "none" in compress_list:
            self.logger.info(
                "Inputs are too big, skipping uncompressed build."
            )
            compress_list.remove("none")

        if not compress_list:
            raise SizeTooBigError()

        # Avoid passing format-specific options unrelated to board format
        image_format_opts = {
            "image_format": self.board.image_format,
        }

        if self.board.image_format == "fit":
            image_format_opts["name"] = self.description
            image_format_opts["patch_dtbs"] = not self.board.loads_fit_ramdisk

            if self.board.fit_ramdisk_load_address is not None:
                image_format_opts["ramdisk_load_address"] = (
                    self.board.fit_ramdisk_load_address
                )

        elif self.board.image_format == "zimage":
            if not self.board.loads_zimage_ramdisk:
                hack = self.zimage_initramfs_hack
                image_format_opts["pad_vmlinuz"] = (hack == "pad-vmlinuz")
                image_format_opts["set_init_size"] = (hack == "set-init-size")

        for compress in compress_list:
            self.logger.info("Trying with compression '{}'.".format(compress))
            tmpdir = self.tmpdir / "mkdepthcharge-{}".format(compress)

            try:
                mkdepthcharge(
                    arch=self.board.arch,
                    cmdline=self.kernel_cmdline,
                    compress=compress,
                    dtbs=dtbs,
                    **image_format_opts,
                    kernel_start=self.board.image_start_address,
                    initramfs=self.initrd,
                    keyblock=self.vboot_keyblock,
                    output=outtmp,
                    signprivate=self.vboot_private_key,
                    signpubkey=self.vboot_public_key,
                    vmlinuz=self.kernel,
                    tmpdir=tmpdir,
                    verbosity=self.verbosity,
                )

            except Exception as err:
                raise CommandExit(
                    "Failed while creating depthcharge image.",
                ) from err

            if outtmp.stat().st_size < self.board.image_max_size:
                break

            self.logger.warning(
                "Image with compression '{}' is too big for this board."
                .format(compress)
            )

        else:
            # The necessary zimage padding might be too big, actually
            # check if reducing the initramfs would make things fit.
            if outtmp.stat().st_size - initrd_size < self.board.image_max_size:
                raise InitramfsSizeTooBigError()
            else:
                raise SizeTooBigError()

        self.logger.info("Copying newly built image to output.")
        try:
            copy(outtmp, self.output)
        except PermissionError as err:
            raise PermissionError(
                "Couldn't copy to '{}', permission denied."
                .format(self.output)
            )

        self.logger.warning(
            "Built depthcharge image for kernel version '{}'."
            .format(self.kernel_release or "(unknown)")
        )
        return self.output

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options

