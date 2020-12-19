#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import (
    __version__,
    LOCALSTATEDIR,
)
from depthcharge_tools.utils import (
    Command,
    Disk,
    Kernel,
    Path,
)

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
            for k in kernels:
                if image == k.release:
                    image = LOCALSTATEDIR / "{}.img".format(k.release)
                    break
            else:
                image = Path(image).resolve()

        image_vblock = image.read_bytes()[:0x10000]

        badparts = []
        for disk in Disk.disks(bootable=True):
            for part in disk.partitions():
                with part.path.open("rb") as p:
                    if p.read(0x10000) == image_vblock:
                        if part.attribute:
                            badparts.append(part)

        current = Disk.by_kern_guid()
        for part in badparts:
            if part.path == current and not force:
                raise ValueError("current")

        for part in badparts:
            part.attribute = 0x000

        if image.parent == LOCALSTATEDIR:
            inputs = LOCALSTATEDIR / "{}.inputs".format(image.name)
            image.unlink()
            if inputs.exists():
                inputs.unlink()

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
