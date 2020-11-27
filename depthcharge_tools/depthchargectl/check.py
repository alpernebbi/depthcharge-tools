#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
)

logger = logging.getLogger(__name__)


def _check(*args, **kwargs):
    print(args, kwargs)


def argument_parser(parent, add_global_options):
    parser = parent.add_parser(
        "check",
        description="Check if a depthcharge image can be booted.",
        help="Check if a depthcharge image can be booted.",
        usage="%(prog)s [options] image",
        add_help=False,
    )

    arguments = parser.add_argument_group(
        title="Positional arguments",
    )
    arguments.add_argument(
        "image",
        nargs="?",
        help="Depthcharge image to check validity of.",
    )

    options = parser.add_argument_group(
        title="Options",
    )
    add_global_options(options)

    return parser
