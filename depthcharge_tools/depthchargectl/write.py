#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__

logger = logging.getLogger(__name__)


def _write(*args, **kwargs):
    print(args, kwargs)


def argument_parser(commands, add_global_options):
    write = commands.add_parser(
        "write",
        description="Write an image to a ChromeOS kernel partition.",
        help="Write an image to a ChromeOS kernel partition.",
        usage="%(prog)s [options] (kernel-image | image)",
        add_help=False,
    )
    write_arguments = write.add_argument_group(
        title="Positional arguments",
    )
    write_image_or_version = write_arguments.add_mutually_exclusive_group(
            required=True,
    )
    write_image_or_version.add_argument(
        "kernel-version",
        nargs="?",
        help="Installed kernel version to write to disk.",
    )
    write_image_or_version.add_argument(
        "image",
        nargs="?",
        help="Depthcharge image to write to disk.",
    )
    write_options = write.add_argument_group(
        title="Options",
    )
    write_options.add_argument(
        "-f", "--force",
        action='store_true',
        help="Write image even if it cannot be verified.",
    )
    write_options.add_argument(
        "-t", "--target",
        metavar="DISK|PART",
        action='store',
        help="Specify a disk or partition to write to.",
    )
    write_options.add_argument(
        "--no-prioritize",
        dest="prioritize",
        action='store_false',
        help="Don't set any flags on the partition.",
    )
    write_options.add_argument(
        "--allow-current",
        action='store_true',
        help="Allow overwriting the currently booted partition.",
    )
    add_global_options(write_options)

