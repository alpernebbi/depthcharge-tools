#! /usr/bin/env python3

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
from depthcharge_tools.utils.os import (
    system_disks,
    Disks,
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

    logger = depthchargectl.logger.getChild("write")
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
    @Argument("-t", "--target", metavar="DISK|PART|MNT")
    def target(self, target):
        """Specify a disk, partition or system to write to."""
        if target is None:
            return None

        if os.path.ismount(Path(target).resolve()):
            self.logger.info(
                "Using target '{}' as the system to write to."
                .format(target)
            )
            return Path(target).resolve()

        self.logger.info(
            "Using target argument '{}' as a device description."
            .format(target)
        )

        return str(target)

    @options.add
    @Argument("--target-mountpoint", metavar="MNT", help=argparse.SUPPRESS)
    def target_mountpoint(self, mnt=None):
        """Root mountpoint of the system to write to."""
        if mnt is not None:
            self.logger.info(
                "Using target mountpoint '{}' from argument."
                .format(mnt)
            )
            return Path(mnt).resolve()

        target = self.target
        if target is None:
            return None

        if isinstance(target, Path):
            return target

        disk = system_disks.evaluate(target)
        mountpoints = sorted(
            system_disks.mountpoints(disk),
            key=lambda p: len(p.parents),
        )

        if len(mountpoints) > 1:
            mnt = mountpoints[0]
            self.logger.warning(
                "Choosing '{}' from multiple target mountpoints: {}."
                .format(mnt, mountpoints)
            )
            return mnt

        elif mountpoints:
            mnt = mountpoints[0]
            if mnt != Path("/").resolve():
                self.logger.info(
                    "Using target mountpoint '{}'."
                    .format(mnt)
                )
            return mnt

        self.logger.warning(
            "Couldn't find target mountpoint, falling back to '/'."
        )

        return Path("/").resolve()

    @options.add
    @Argument("--target-devices", metavar="DISK|PART", help=argparse.SUPPRESS)
    def target_devices(self, *devices):
        """Bootable disks of the system to write to."""
        if devices:
            self.logger.info(
                "Using target devices '{}' from given argument."
                .format(devices)
            )
            return devices

        target = self.target
        if target is None:
            return []

        if isinstance(target, str):
            device = system_disks.evaluate(target)
            return [device] if device else []

        disks = Disks(
            fstab=(target / "etc" / "fstab"),
            crypttab=(target / "etc" / "crypttab"),
        )
        devices = disks.bootable_disks()
        if devices:
            self.logger.info(
                "Using target devices '{}' from target mountpoint."
                .format(devices)
            )
            return devices

        raise ValueError(
            "Could not find devices for target '{}'"
            .format(target)
        )

    @options.add
    @Argument("--no-prioritize", prioritize=False)
    def prioritize(self, prioritize=True):
        """Don't set any flags on the partition."""
        return prioritize

    @options.add
    @Argument("--allow-current", allow=True)
    def allow_current(self, allow=False):
        """Allow overwriting the currently booted partition."""
        return allow

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
                    root=self.target,
                    config=self.config,
                    board=self.board,
                    tmpdir=self.tmpdir / "build",
                    images_dir=self.images_dir,
                    vboot_keyblock=self.vboot_keyblock,
                    vboot_public_key=self.vboot_public_key,
                    vboot_private_key=self.vboot_private_key,
                    kernel_cmdline=self.kernel_cmdline,
                    ignore_initramfs=self.ignore_initramfs,
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
                disks=self.target_devices,
                min_size=image.stat().st_size,
                allow_current=self.allow_current,
                config=self.config,
                board=self.board,
                tmpdir=self.tmpdir / "target",
                images_dir=self.images_dir,
                vboot_keyblock=self.vboot_keyblock,
                vboot_public_key=self.vboot_public_key,
                vboot_private_key=self.vboot_private_key,
                kernel_cmdline=self.kernel_cmdline,
                ignore_initramfs=self.ignore_initramfs,
                verbosity=self.verbosity,
            )

        except Exception as err:
            raise NoUsableCrosPartitionError() from err

        if target is None:
            raise NoUsableCrosPartitionError()

        self.logger.info("Targeted partition '{}'.".format(target))

        # Check and warn if we targeted the currently booted partition,
        # as that usually means it's the only partition.
        current = system_disks.by_kern_guid()
        if self.allow_current and target.path == current.path:
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

        if self.prioritize:
            self.logger.info(
                "Setting '{}' as the highest-priority bootable part."
                .format(target)
            )

            try:
                target.attribute = 0x010
            except subprocess.CalledProcessError as err:
                raise CommandExit(
                    "Failed to set attributes for partition '{}'."
                    .format(target)
                ) from err

            try:
                target.prioritize()
            except subprocess.CalledProcessError as err:
                raise CommandExit(
                    "Failed to prioritize partition '{}'."
                    .format(target)
                ) from err

            self.logger.warning(
                "Set partition '{}' as next to boot."
                .format(target)
            )

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options

