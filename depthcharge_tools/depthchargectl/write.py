#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Command,
)

logger = logging.getLogger(__name__)


def _write(*args, **kwargs):
    print(args, kwargs)


class DepthchargectlWrite(Command):
    def __init__(self, name="depthchargectl write", parent=None):
        super().__init__(name, parent)

    def _init_parser(self):
        return super()._init_parser(
            description="Write an image to a ChromeOS kernel partition.",
            usage="%(prog)s [options] (kernel-image | image)",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        image_or_version = arguments.add_mutually_exclusive_group(
                required=True,
        )
        image_or_version.add_argument(
            "kernel-version",
            nargs="?",
            help="Installed kernel version to write to disk.",
        )
        image_or_version.add_argument(
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
