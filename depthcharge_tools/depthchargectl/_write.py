#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl write subcommand
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import argparse
import logging
import os
import subprocess

from pathlib import Path

from depthcharge_tools import (
    __version__,
)
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
    CommandExit,
)
from depthcharge_tools.utils.platform import (
    KernelEntry,
    installed_kernels,
)

from depthcharge_tools.depthchargectl import depthchargectl


class ImageBuildError(CommandExit):
    def __init__(self, kernel_version=None):
        self.kernel_version = kernel_version

        if kernel_version is None:
            message = "Failed to build depthcharge image."

        else:
            message = (
                "Failed to build depthcharge image for kernel version '{}'."
                .format(kernel_version)
            )

        super().__init__(message=message)


class NotBootableImageError(CommandExit):
    def __init__(self, image):
        self.image = image
        super().__init__(
            "Image '{}' is not bootable on this board."
            .format(image)
        )


class NoUsableCrosPartitionError(CommandExit):
    def __init__(self):
        super().__init__(
            "No usable Chrome OS Kernel partition found."
        )


@depthchargectl.subcommand("write")
class depthchargectl_write(
    depthchargectl,
    prog="depthchargectl write",
    usage="%(prog)s [options] [KERNEL-VERSION | IMAGE]",
    add_help=False,
):
    """Write an image to a ChromeOS kernel partition."""

    _logger = depthchargectl._logger.getChild("write")
    config_section = "depthchargectl/write"

    @depthchargectl.board.copy()
    def board(self, codename=""):
        """Assume we're running on the specified board"""
        # We can write images to partitions without knowing the board.
        # The image argument will become required if this returns None.
        try:
            return super().board
        except Exception as err:
            self.logger.warning(err)
            return None

    @Group
    def positionals(self):
        """Positional arguments"""

        if self.image is not None and self.kernel_version is not None:
            raise ValueError(
                "Image and kernel_version arguments are mutually exclusive"
            )

        arg = self.image or self.kernel_version

        # Turn arg into a relevant KernelEntry if it's a kernel version
        # or a Path() if not
        if isinstance(arg, str):
            arg = max(
                (k for k in installed_kernels() if k.release == arg),
                default=Path(arg).resolve(),
            )

        if isinstance(arg, KernelEntry):
            self.image = None
            self.kernel_version = arg

        elif isinstance(arg, Path):
            self.image = arg
            self.kernel_version = None

        if self.board is None and self.image is None:
            raise ValueError(
                "An image file is required when no board is specified."
            )

    @positionals.add
    @Argument(dest=argparse.SUPPRESS, nargs=0)
    def kernel_version(self, kernel_version):
        """Installed kernel version to write to disk."""
        return kernel_version

    @positionals.add
    @Argument
    def image(self, image=None):
        """Depthcharge image to write to disk."""
        return image

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-f", "--force", force=True)
    def force(self, force=False):
        """Write image even if it cannot be verified."""
        return force

    @options.add
    @Argument("-t", "--target", metavar="DISK|PART")
    def target(self, target):
        """Specify a disk or partition to write to."""
        return target

    @options.add
    @Argument("--allow-current", allow=True)
    def allow_current(self, allow=False):
        """Allow overwriting the currently booted partition."""
        return allow

    @options.add
    @Argument("--no-prioritize", bless=None,
              help="Don't set any flags on the partition.")
    @Argument("--oneshot", bless="oneshot",
              help="Set the partition to be tried once.")
    @Argument("--bad", bless="bad",
              help="Set the partition as unbootable.")
    @Argument("--bless", bless="good",
              help="Set the partition as always bootable.")
    def bless(self, bless=True):
        """Set partition as bootable after writing"""
        if bless in ("good", "oneshot", "bad"):
            return bless
        if bless is True:
            return "oneshot"
        if bless in (False, None):
            return None

        raise ValueError(
            "Bless argument must be either good, oneshot, or bad."
        )

    @Group
    def build_options(self):
        """Image build options"""
        # Resolve image argument through its Group first
        self.positionals

        if any((
            self.kernel_release,
            self.kernel,
            self.initrd,
            self.fdtdir,
            self.dtbs,
            self.description,
            self.compress,
            self.timestamp,
            self.output,
        )) and self.image is not None:
            raise ValueError(
                "Image build options are incompatible with image argument."
            )

    @build_options.add
    @Argument("--kernel-release", nargs=1)
    def kernel_release(self, name=None):
        """Release name for the kernel used in image."""
        return name

    @build_options.add
    @Argument("--kernel", nargs=1)
    def kernel(self, file_=None):
        """Kernel executable."""
        return file_

    @build_options.add
    @Argument("--initramfs", nargs='+')
    def initrd(self, *files):
        """Ramdisk images."""
        return files

    @build_options.add
    @Argument("--fdtdir", nargs=1)
    def fdtdir(self, dir_=None):
        """Directory to search device-tree binaries for the board."""
        return dir_

    @build_options.add
    @Argument("--dtbs", nargs="+", metavar="FILE")
    def dtbs(self, *files):
        """Device-tree binary files to use instead of searching fdtdir."""
        return files

    @build_options.add
    @Argument("--description", nargs=1)
    def description(self, desc=None):
        """Human-readable description for the image."""
        return desc

    @build_options.add
    @Argument("--compress", nargs="+", metavar="TYPE")
    def compress(self, *compress):
        """Compression types to attempt."""
        return compress

    @build_options.add
    @Argument("--timestamp", nargs=1)
    def timestamp(self, seconds=None):
        """Build timestamp for the image"""
        return seconds

    @build_options.add
    @Argument("-o", "--output", nargs=1)
    def output(self, path=None):
        """Output image to path instead of storing in images-dir"""
        return path

    def __call__(self):
        if self.board is None:
            self.logger.warning(
                "Using given image '{}' without board-specific checks."
                .format(self.image)
            )
            image = self.image

        elif self.image is not None:
            self.logger.info("Using given image '{}'." .format(self.image))
            image = self.image

            try:
                depthchargectl.check(
                    image=image,
                    config=self.config,
                    board=self.board,
                    tmpdir=self.tmpdir / "check",
                    images_dir=self.images_dir,
                    vboot_keyblock=self.vboot_keyblock,
                    vboot_public_key=self.vboot_public_key,
                    vboot_private_key=self.vboot_private_key,
                    kernel_cmdline=self.kernel_cmdline,
                    ignore_initramfs=self.ignore_initramfs,
                    zimage_initramfs_hack=self.zimage_initramfs_hack,
                    verbosity=self.verbosity,
                )

            except Exception as err:
                if self.force:
                    self.logger.warning(
                        "Image '{}' is not bootable on this board, "
                        "continuing due to --force."
                        .format(image)
                    )

                else:
                    raise NotBootableImageError(image) from err

        else:
            # No image given, try creating one.
            try:
                image = depthchargectl.build_(
                    kernel_version=self.kernel_version,
                    kernel_release=self.kernel_release,
                    kernel=self.kernel,
                    initrd=self.initrd,
                    fdtdir=self.fdtdir,
                    dtbs=self.dtbs,
                    description=self.description,
                    output=self.output,
                    compress=self.compress,
                    timestamp=self.timestamp,
                    root=self.root,
                    root_mountpoint=self.root_mountpoint,
                    boot_mountpoint=self.boot_mountpoint,
                    config=self.config,
                    board=self.board,
                    tmpdir=self.tmpdir / "build",
                    images_dir=self.images_dir,
                    vboot_keyblock=self.vboot_keyblock,
                    vboot_public_key=self.vboot_public_key,
                    vboot_private_key=self.vboot_private_key,
                    kernel_cmdline=self.kernel_cmdline,
                    ignore_initramfs=self.ignore_initramfs,
                    zimage_initramfs_hack=self.zimage_initramfs_hack,
                    verbosity=self.verbosity,
                )

            except Exception as err:
                raise ImageBuildError(self.kernel_version) from err

        # We don't want target to unconditionally avoid the current
        # partition since we will also check that here. But whatever we
        # choose must be bigger than the image we'll write to it.
        self.logger.info("Searching disks for a target partition.")
        try:
            target = depthchargectl.target(
                disks=[self.target] if self.target else [],
                min_size=image.stat().st_size,
                allow_current=self.allow_current,
                root=self.root,
                root_mountpoint=self.root_mountpoint,
                boot_mountpoint=self.boot_mountpoint,
                config=self.config,
                board=self.board,
                tmpdir=self.tmpdir / "target",
                images_dir=self.images_dir,
                vboot_keyblock=self.vboot_keyblock,
                vboot_public_key=self.vboot_public_key,
                vboot_private_key=self.vboot_private_key,
                kernel_cmdline=self.kernel_cmdline,
                ignore_initramfs=self.ignore_initramfs,
                zimage_initramfs_hack=self.zimage_initramfs_hack,
                verbosity=self.verbosity,
            )

        except Exception as err:
            raise NoUsableCrosPartitionError() from err

        if target is None:
            raise NoUsableCrosPartitionError()

        self.logger.info("Targeted partition '{}'.".format(target))

        # Check and warn if we targeted the currently booted partition,
        # as that usually means it's the only partition.
        current = self.diskinfo.by_kern_guid()
        if current is not None and self.allow_current and target.path == current.path:
            self.logger.warning(
                "Overwriting the currently booted partition '{}'. "
                "This might make your system unbootable."
                .format(target)
            )

        self.logger.info(
            "Writing image '{}' to partition '{}'."
            .format(image, target)
        )
        target.write_bytes(image.read_bytes())
        self.logger.warning(
            "Wrote image '{}' to partition '{}'."
            .format(image, target)
        )

        if self.bless is not None:
            if self.bless == "good":
                self.logger.info(
                    "Setting '{}' as the highest-priority bootable part."
                    .format(target)
                )
            elif self.bless == "oneshot":
                self.logger.info(
                    "Setting '{}' as the highest-priority once-bootable part."
                    .format(target)
                )
            elif self.bless == "bad":
                self.logger.info(
                    "Setting '{}' as an unbootable part."
                    .format(target)
                )

            try:
                depthchargectl.bless(
                    partition=target,
                    oneshot=(self.bless == "oneshot"),
                    bad=(self.bless == "bad"),
                    root=self.root,
                    root_mountpoint=self.root_mountpoint,
                    boot_mountpoint=self.boot_mountpoint,
                    config=self.config,
                    board=self.board,
                    tmpdir=self.tmpdir / "bless",
                    images_dir=self.images_dir,
                    vboot_keyblock=self.vboot_keyblock,
                    vboot_public_key=self.vboot_public_key,
                    vboot_private_key=self.vboot_private_key,
                    kernel_cmdline=self.kernel_cmdline,
                    ignore_initramfs=self.ignore_initramfs,
                    zimage_initramfs_hack=self.zimage_initramfs_hack,
                    verbosity=self.verbosity,
                )
            except Exception as err:
                raise CommandExit(
                    "Failed to set flags on partition '{}'."
                    .format(target)
                ) from err

            if self.bless in ("good", "oneshot"):
                self.logger.warning(
                    "Set partition '{}' as next to boot."
                    .format(target)
                )
            elif self.bless == "bad":
                self.logger.info(
                    "Set partition '{}' as unbootable."
                    .format(target)
                )

        return target

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options

