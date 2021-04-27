#! /usr/bin/env python3

import argparse
import logging

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

    logger = depthchargectl.logger.getChild("remove")
    config_section = "depthchargectl/remove"

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
    @Argument(dest=argparse.SUPPRESS, nargs=argparse.SUPPRESS)
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
        for disk in system_disks.bootable_disks():
            for part in disk.cros_partitions():
                self.logger.info("Checking partition '{}'.".format(part))

                # It's OK to check only the vblock header, as that
                # contains signatures on the content and those will be
                # different if the content is different.
                with part.path.open("rb") as p:
                    if p.read(0x10000) == image_vblock:
                        if part.attribute:
                            badparts.append(part)

        if not badparts:
            self.logger.warn("No active partitions contain the given image.")

        current = system_disks.by_kern_guid()
        if current in badparts:
            if self.force:
                self.logger.warn(
                    "Deactivating the currently booted partition '{}'. "
                    "This might make your system unbootable."
                    .format(current)
                )
            else:
                raise BootedPartitionError(current)

        for part in badparts:
            self.logger.info("Deactivating '{}'.".format(part))
            part.attribute = 0x000
            self.logger.warn("Deactivated '{}'.".format(part))

        if image.parent == self.images_dir:
            self.logger.info(
                "Image '{}' is in images dir, deleting."
                .format(image)
            )
            image.unlink()
            self.logger.warn("Deleted image '{}'.".format(image))

        else:
            self.logger.info("Not deleting image file '{}'.")

        if badparts:
            return badparts

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
