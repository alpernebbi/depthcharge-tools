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


def argument_parser(commands, add_global_options):
    check = commands.add_parser(
        "check",
        description="Check if a depthcharge image can be booted.",
        help="Check if a depthcharge image can be booted.",
        usage="%(prog)s [options] image",
        add_help=False,
    )
    check_arguments = check.add_argument_group(
        title="Positional arguments",
    )
    check_arguments.add_argument(
        "image",
        nargs="?",
        help="Depthcharge image to check validity of.",
    )
    check_options = check.add_argument_group(
        title="Options",
    )
    add_global_options(check_options)

