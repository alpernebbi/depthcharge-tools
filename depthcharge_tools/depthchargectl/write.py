#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import (
    __version__,
    LOCALSTATEDIR,
)
from depthcharge_tools.utils import (
    Command,
    Kernel,
    Path,
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

        if image is None:
            image = self._parent.build(max(kernels).release)

        elif isinstance(image, str):
            for k in kernels:
                if image == k.release:
                    image = self._parent.build(k.release)
                    break
            else:
                image = Path(image).resolve()

        try:
            self._parent.check(image)
        except Exception as err:
            if not force:
                raise

        target = self._parent.target(
            disks=[target] if target else None,
            min_size=image.stat().st_size,
            allow_current=allow_current,
        )

        if target is None:
            raise RuntimeError("target")

        if target.path is None:
            raise RuntimeError("target path")

        target.attribute = 0x010
        target.path.write_bytes(image.read_bytes())

        if prioritize:
            target.prioritize()


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
