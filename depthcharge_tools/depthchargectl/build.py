#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
    Command,
)

logger = logging.getLogger(__name__)


def _build(*args, **kwargs):
    print(args, kwargs)


class DepthchargectlBuild(Command):
    def __init__(self, name="depthchargectl build", parent=None):
        super().__init__(name, parent)

    def _init_parser(self):
        return super()._init_parser(
            description="Buld a depthcharge image for the running system.",
            usage="%(prog)s [options] [kernel-version]",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            "kernel_version",
            metavar="kernel-version",
            nargs="?",
            help="Installed kernel version to build an image for.",
        )

    def _init_options(self, options):
        options.add_argument(
            "-a", "--all",
            action='store_true',
            help="Build images for all available kernel versions.",
        )
        options.add_argument(
            "-f", "--force",
            action='store_true',
            help="Rebuild images even if existing ones are valid.",
        )
        options.add_argument(
            "--reproducible",
            action='store_true',
            help="Try to build reproducible images.",
        )
