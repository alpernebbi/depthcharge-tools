#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__

logger = logging.getLogger(__name__)


def _rm(*args, **kwargs):
    print(args, kwargs)


def argument_parser(parent, add_global_options):
    parser = parent.add_parser(
        "rm",
        description="Remove images and disable partitions containing them.",
        help="Remove images and disable partitions containing them.",
        usage="%(prog)s [options] (kernel-version | image)",
        add_help=False,
    )
    arguments = parser.add_argument_group(
        title="Positional arguments",
    )
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

    options = parser.add_argument_group(
        title="Options",
    )
    options.add_argument(
        "-f", "--force",
        action='store_true',
        help="Allow removing the currently booted partition.",
    )
    add_global_options(options)

    return parser
