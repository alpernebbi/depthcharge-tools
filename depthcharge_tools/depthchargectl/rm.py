#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import (
    __version__,
)
from depthcharge_tools.utils import (
    Disk,
    Kernel,
    Path,
)
from depthcharge_tools.utils import OldCommand as Command

logger = logging.getLogger(__name__)


class DepthchargectlRm(Command):
    def __init__(self, name="depthchargectl rm", parent=None):
        super().__init__(name, parent)

    def __call__(
        self,
        image,
        force=False,
    ):
        kernels = Kernel.all()

        if isinstance(image, str):
            # This can be run after the kernel is uninstalled, where the
            # version would no longer be valid, so don't check for that.
            # Instead just check if we have it as an image.
            images = Path("/boot/depthcharge-tools/images")
            img = (images / "{}.img".format(image)).resolve()
            if img.parent == images and img.is_file():
                logger.info(
                    "Disabling partitions for kernel version '{}'."
                    .format(image)
                )
                image = img

            else:
                image = Path(image).resolve()
                logger.info(
                    "Disabling partitions for depthcharge image '{}'."
                    .format(image)
                )

        if not image.is_file():
            raise ValueError(
                "Image to remove '{}' is not a file."
                .format(image)
            )

        # When called with --vblockonly vbutil_kernel creates a file of
        # size 64KiB == 0x10000.
        image_vblock = image.read_bytes()[:0x10000]

        logger.info(
            "Searching for Chrome OS Kernel partitions containing '{}'."
            .format(image)
        )
        badparts = []
        for disk in Disk.disks(bootable=True):
            for part in disk.partitions():
                logger.info("Checking partition '{}'.".format(part))

                # It's OK to check only the vblock header, as that
                # contains signatures on the content and those will be
                # different if the content is different.
                with part.path.open("rb") as p:
                    if p.read(0x10000) == image_vblock:
                        if part.attribute:
                            badparts.append(part)

        if not badparts:
            logger.info("No partitions contain the given image.")

        current = Disk.by_kern_guid()
        for part in badparts:
            if part.path == current and not force:
                raise ValueError(
                    "Refusing to disable currently booted partition."
                )

        for part in badparts:
            logger.info("Deactivating '{}'.".format(part))
            part.attribute = 0x000
            logger.info("Deactivated '{}'.".format(part))

        if image.parent == images:
            logger.info(
                "Image '{}' is in images dir, deleting."
                .format(image)
            )

            inputs = images / "{}.inputs".format(image.name)
            image.unlink()
            logger.info("Deleted image '{}'.".format(image))

            if inputs.exists():
                inputs.unlink()
                logger.info("Deleted inputs file '{}'.".format(inputs))

        else:
            logger.info("Not deleting image file '{}'.")

        if badparts:
            return badparts

    def _init_parser(self):
        return super()._init_parser(
            description="Remove images and disable partitions containing them.",
            usage="%(prog)s [options] (kernel-version | image)",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            dest=argparse.SUPPRESS,
            metavar="kernel-version",
            nargs=argparse.SUPPRESS,
            help="Installed kernel version to disable.",
        )
        arguments.add_argument(
            "image",
            help="Depthcharge image to disable.",
        )

    def _init_options(self, options):
        options.add_argument(
            "-f", "--force",
            action='store_true',
            help="Allow removing the currently booted partition.",
        )
