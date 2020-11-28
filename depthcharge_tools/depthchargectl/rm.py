#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Command,
)

logger = logging.getLogger(__name__)


class DepthchargectlRm(Command):
    def __init__(self, name="depthchargectl rm", parent=None):
        super().__init__(name, parent)

    def __call__(self, *args, **kwargs):
        print(args, kwargs)

    def _init_parser(self):
        return super()._init_parser(
            description="Remove images and disable partitions containing them.",
            usage="%(prog)s [options] (kernel-version | image)",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        image_or_version = arguments.add_mutually_exclusive_group(
            required=True,
        )
        image_or_version.add_argument(
            "kernel-version",
            nargs="?",
            help="Installed kernel version to disable.",
        )
        image_or_version.add_argument(
            "image",
            nargs="?",
            help="Depthcharge image to disable.",
        )

    def _init_options(self, options):
        options.add_argument(
            "-f", "--force",
            action='store_true',
            help="Allow removing the currently booted partition.",
        )
