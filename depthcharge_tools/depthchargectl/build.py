#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
)

logger = logging.getLogger(__name__)


def _build(*args, **kwargs):
    print(args, kwargs)


def argument_parser(parent, add_global_options):
    parser = parent.add_parser(
        "build",
        description="Buld a depthcharge image for the running system.",
        help="Buld a depthcharge image for the running system.",
        usage="%(prog)s [options] [kernel-version]",
        add_help=False,
    )

    arguments = parser.add_argument_group(
        title="Positional arguments",
    )
    arguments.add_argument(
        "kernel_version",
        metavar="kernel-version",
        nargs="?",
        help="Installed kernel version to build an image for.",
    )

    options = parser.add_argument_group(
        title="Options",
    )
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
    add_global_options(build_options)

    return parser
