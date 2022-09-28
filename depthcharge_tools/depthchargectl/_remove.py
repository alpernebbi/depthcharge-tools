#! /usr/bin/env python3

import argparse
import logging
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

from depthcharge_tools.depthchargectl import depthchargectl


class BootedPartitionError(CommandExit):
    def __init__(self, partition):
        self.partition = partition
        super().__init__(
            "Refusing to disable currently booted partition '{}'."
            .format(partition)
        )


@depthchargectl.subcommand("remove")
class depthchargectl_remove(
    depthchargectl,
    prog="depthchargectl remove",
    usage="%(prog)s [options] (KERNEL_VERSION | IMAGE)",
    add_help=False,
):
    """Remove images and disable partitions containing them."""

    _logger = depthchargectl._logger.getChild("remove")
    config_section = "depthchargectl/remove"

    @depthchargectl.board.copy()
    def board(self, codename=""):
        """Assume we're running on the specified board"""
        # We can disable partitions without knowing the board.
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
                "Image and kernel_version arguments are mutually exclusive."
            )

        if self.image is not None:
            image = self.image
        else:
            image = self.kernel_version

        if isinstance(image, str):
            # This can be run after the kernel is uninstalled, where the
            # version would no longer be valid, so don't check for that.
            # Instead just check if we have it as an image.
            img = (self.images_dir / "{}.img".format(image)).resolve()
            if img.parent == self.images_dir and img.is_file():
                self.logger.info(
                    "Disabling partitions for kernel version '{}'."
                    .format(image)
                )
                self.image = img
                self.kernel_version = image

            else:
                self.image = Path(image).resolve()
                self.kernel_version = None
                self.logger.info(
                    "Disabling partitions for depthcharge image '{}'."
                    .format(image)
                )

        if not self.image.is_file():
            raise TypeError(
                "Image to remove '{}' is not a file."
                .format(self.image)
            )

    @positionals.add
    @Argument(dest=argparse.SUPPRESS, nargs=0)
    def kernel_version(self, kernel_version):
        """Installed kernel version to disable."""
        return kernel_version

    @positionals.add
    @Argument
    def image(self, image):
        """Depthcharge image to disable."""
        return image

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-f", "--force", force=True)
    def force(self, force=False):
        """Allow disabling the currently booted partition."""
        return force

    def __call__(self):
        image = self.image

        # When called with --vblockonly vbutil_kernel creates a file of
        # size 64KiB == 0x10000.
        image_vblock = image.read_bytes()[:0x10000]

        self.logger.info(
            "Searching for Chrome OS Kernel partitions containing '{}'."
            .format(image)
        )
        badparts = []
        error_disks = []
        for disk in self.diskinfo.bootable_disks():
            try:
                parts = disk.cros_partitions()
            except subprocess.CalledProcessError as err:
                error_disks.append(disk)
                self.logger.debug(
                    "Couldn't get partitions for disk '{}'."
                    .format(disk)
                )
                self.logger.debug(
                    err,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG),
                )
                continue

            for part in parts:
                self.logger.info("Checking partition '{}'.".format(part))

                # It's OK to check only the vblock header, as that
                # contains signatures on the content and those will be
                # different if the content is different.
                with part.path.open("rb") as p:
                    if p.read(0x10000) == image_vblock:
                        try:
                            if part.attribute:
                                badparts.append(part)
                        except subprocess.CalledProcessError as err:
                            self.logger.warning(
                                "Couldn't get attribute for partition '{}'."
                                .format(part)
                            )
                            self.logger.debug(
                                err,
                                exc_info=self.logger.isEnabledFor(
                                    logging.DEBUG,
                                ),
                            )

        current = self.diskinfo.by_kern_guid()
        if current in badparts:
            if self.force:
                self.logger.warning(
                    "Deactivating the currently booted partition '{}'. "
                    "This might make your system unbootable."
                    .format(current)
                )
            else:
                raise BootedPartitionError(current)

        done_parts = []
        error_parts = []
        for part in badparts:
            self.logger.info("Deactivating '{}'.".format(part))
            try:
                part.attribute = 0x000
            except subprocess.CalledProcessError as err:
                error_parts.append(part)
                self.logger.debug(
                    "Couldn't zero attributes for partition '{}'."
                    .format(part)
                )
                self.logger.debug(
                    err,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG),
                )
                continue

            done_parts.append(part)
            self.logger.warning("Deactivated '{}'.".format(part))

        if image.parent == self.images_dir:
            self.logger.info(
                "Image '{}' is in images dir, deleting."
                .format(image)
            )
            image.unlink()
            self.logger.warning("Deleted image '{}'.".format(image))

        else:
            self.logger.info(
                "Not deleting image file '{}'."
                .format(image)
            )

        output = badparts or None

        error_msg = []
        if error_disks:
            error_msg.append(
                "Couldn't disable partitions for disks {}."
                .format(error_disks)
            )

        if error_parts:
            error_msg.append(
                "Couldn't disable partitions {}."
                .format(error_parts)
            )

        if error_msg:
            return CommandExit(
                message="\n".join(error_msg),
                output=done_parts,
                returncode=1,
            )

        if not output:
            self.logger.warning(
                "No active partitions contain the given image."
            )

        return output

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
