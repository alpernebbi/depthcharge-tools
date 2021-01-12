#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import (
    __version__,
)
from depthcharge_tools.utils import (
    Command,
    Kernel,
    Path,
    Disk,
)

logger = logging.getLogger(__name__)


class DepthchargectlWrite(Command):
    def __init__(self, name="depthchargectl write", parent=None):
        super().__init__(name, parent)

    def __call__(
        self,
        image=None,
        force=False,
        target=None,
        prioritize=True,
        allow_current=False,
    ):
        kernels = Kernel.all()

        # No image given, try creating one.
        if image is None:
            version = max(kernels).release
            logger.info(
                "Using image for newest installed kernel version '{}'."
                .format(version)
            )
            image = self._parent.build(version)

        elif isinstance(image, str):
            for k in kernels:
                if image == k.release:
                    logger.info(
                        "Using image for given kernel version '{}'."
                        .format(k.release)
                    )
                    image = self._parent.build(k.release)
                    break
            else:
                image = Path(image).resolve()
                logger.info("Using given image '{}'.".format(image))

        try:
            # This also checks if the machine is supported.
            self._parent.check(image)
        except Exception as err:
            if force:
                logger.warn(
                    "Depthcharge image '{}' is not bootable on this "
                    "board, continuing due to --force."
                    .format(image)
                )
            else:
                raise ValueError(
                    "Depthcharge image '{}' is not bootable on this "
                    "board."
                    .format(image)
                )

        # We don't want target to unconditionally avoid the current
        # partition since we will also check that here. But whatever we
        # choose must be bigger than the image we'll write to it.
        logger.info("Searching disks for a target partition.")
        try:
            target = self._parent.target(
                disks=[target] if target else None,
                min_size=image.stat().st_size,
                allow_current=allow_current,
            )
        except:
            raise ValueError(
                "Couldn't find a usable partition to write to."
            )

        if target.path is None:
            raise ValueError(
                "Cannot write to target partition '{}' without a path."
                .format(target)
            )

        logger.info("Targeted partition '{}'.".format(target))

        # Check and warn if we targeted the currently booted partition,
        # as that usually means it's the only partition.
        current = Disk.by_kern_guid()
        if allow_current and target.path == current:
            logger.warn(
                "Overwriting the currently booted partition '{}'. "
                "This might make your system unbootable."
                .format(target)
            )

        logger.info(
            "Writing depthcharge image '{}' to partition '{}'."
            .format(image, target)
        )
        target.path.write_bytes(image.read_bytes())
        logger.info(
            "Wrote depthcharge image '{}' to partition '{}'."
            .format(image, target)
        )

        if prioritize:
            logger.info(
                "Setting '{}' as the highest-priority bootable part."
                .format(target)
            )
            target.attribute = 0x010
            target.prioritize()
            logger.info(
                "Set partition '{}' as next to boot."
                .format(target)
            )

    def _init_parser(self):
        return super()._init_parser(
            description="Write an image to a ChromeOS kernel partition.",
            usage="%(prog)s [options] (kernel-image | image)",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            dest=argparse.SUPPRESS,
            metavar="kernel-version",
            nargs=argparse.SUPPRESS,
            help="Installed kernel version to write to disk.",
        )
        arguments.add_argument(
            "image",
            nargs="?",
            help="Depthcharge image to write to disk.",
        )

    def _init_options(self, options):
        options.add_argument(
            "-f", "--force",
            action='store_true',
            help="Write image even if it cannot be verified.",
        )
        options.add_argument(
            "-t", "--target",
            metavar="DISK|PART",
            action='store',
            help="Specify a disk or partition to write to.",
        )
        options.add_argument(
            "--no-prioritize",
            dest="prioritize",
            action='store_false',
            help="Don't set any flags on the partition.",
        )
        options.add_argument(
            "--allow-current",
            action='store_true',
            help="Allow overwriting the currently booted partition.",
        )
