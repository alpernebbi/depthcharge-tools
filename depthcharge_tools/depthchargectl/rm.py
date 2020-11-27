#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__

logger = logging.getLogger(__name__)


def _rm(*args, **kwargs):
    print(args, kwargs)


def argument_parser(commands, add_global_options):
    rm = commands.add_parser(
        "rm",
        description="Remove images and disable partitions containing them.",
        help="Remove images and disable partitions containing them.",
        usage="%(prog)s [options] (kernel-version | image)",
        add_help=False,
    )
    rm_arguments = rm.add_argument_group(
        title="Positional arguments",
    )
    rm_image_or_version = rm_arguments.add_mutually_exclusive_group(
            required=True,
    )
    rm_image_or_version.add_argument(
        "kernel-version",
        nargs="?",
        help="Installed kernel version to disable.",
    )
    rm_image_or_version.add_argument(
        "image",
        nargs="?",
        help="Depthcharge image to disable.",
    )
    rm_options = rm.add_argument_group(
        title="Options",
    )
    rm_options.add_argument(
        "-f", "--force",
        action='store_true',
        help="Allow removing the currently booted partition.",
    )
    add_global_options(rm_options)

