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


def _check(*args, **kwargs):
    print(args, kwargs)


class DepthchargectlCheck(Command):
    def __init__(self, name="depthchargectl check", parent=None):
        super().__init__(name, parent)

    def _init_parser(self):
        return super()._init_parser(
            description="Check if a depthcharge image can be booted.",
            usage="%(prog)s [options] image",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            "image",
            nargs="?",
            help="Depthcharge image to check validity of.",
        )
