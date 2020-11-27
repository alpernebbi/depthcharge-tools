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


def argument_parser(commands, add_global_options):
    build = commands.add_parser(
        "build",
        description="Buld a depthcharge image for the running system.",
        help="Buld a depthcharge image for the running system.",
        usage="%(prog)s [options] [kernel-version]",
        add_help=False,
    )
    build_arguments = build.add_argument_group(
        title="Positional arguments",
    )
    build_arguments.add_argument(
        "kernel_version",
        metavar="kernel-version",
        nargs="?",
        help="Installed kernel version to build an image for.",
    )
    build_options = build.add_argument_group(
        title="Options",
    )
    build_options.add_argument(
        "-a", "--all",
        action='store_true',
        help="Build images for all available kernel versions.",
    )
    build_options.add_argument(
        "-f", "--force",
        action='store_true',
        help="Rebuild images even if existing ones are valid.",
    )
    build_options.add_argument(
        "--reproducible",
        action='store_true',
        help="Try to build reproducible images.",
    )
    add_global_options(build_options)
