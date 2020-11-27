#! /usr/bin/env python3

import argparse
import logging
import sys
import types

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
)

logger = logging.getLogger(__name__)


def _target(
    disks=None,
    min_size=None,
    allow_current=False,
):
    if not disks:
        disks = Disk.disks(bootable=True)

    partitions = []
    for d in disks:
        try:
            partitions.append(Partition(d))
        except:
            partitions.extend(Disk(d).partitions())

    good_partitions = []
    for p in partitions:
        if min_size is not None and p.size < int(min_size):
            continue
        if not allow_current and p.path == Disk.by_kern_guid():
            continue
        good_partitions.append(p)

    good_partitions = sorted(
        good_partitions,
        key=lambda p: (p.successful, p.priority, p.tries, p.size),
    )

    if good_partitions:
        print(good_partitions[0])


def argument_parser(parent, add_global_options):
    parser = parent.add_parser(
        "target",
        description="Choose or validate a ChromeOS Kernel partition to use.",
        help="Choose or validate a ChromeOS Kernel partition to use.",
        usage="%(prog)s [options] [partition | disk ...]",
        add_help=False,
    )

    arguments = parser.add_argument_group(
        title="Positional arguments",
    )
    arguments.add_argument(
        "partition",
        nargs=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="Chrome OS kernel partition to validate.",
    )
    arguments.add_argument(
        "disks",
        nargs="*",
        help="Disks to search for an appropriate Chrome OS kernel partition.",
    )

    options = parser.add_argument_group(
        title="Options",
    )
    options.add_argument(
        "-s", "--min-size",
        metavar="BYTES",
        action='store',
        help="Target partitions larger than this size.",
    )
    options.add_argument(
        "--allow-current",
        action='store_true',
        help="Allow targeting the currently booted partition.",
    )
    add_global_options(options)

    return parser
