#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
)

logger = logging.getLogger(__name__)


def _partitions(
    disks=None,
    headings=True,
    all_disks=False,
    output=None,
):
    if all_disks:
        disks = Disk.disks()
    elif disks:
        disks = Disk.disks(*disks)
    else:
        disks = Disk.disks(bootable=True)

    if output is None:
        output = "S,P,T,PATH"
    elif isinstance(output, list):
        output = ",".join(output)

    formats = {
        "SUCCESSFUL": "{0.successful}",
        "PRIORITY": "{0.priority}",
        "TRIES": "{0.tries}",
        "S": "{0.successful}",
        "P": "{0.priority}",
        "T": "{0.tries}",
        "PATH": "{0.path}",
        "DISKPATH": "{0.disk.path}",
        "PARTNO": "{0.partno}",
        "SIZE": "{0.size}",
    }

    columns = output.split(',')
    rows = []

    if headings:
        rows.append(list(columns))

    for disk in disks:
        for part in disk.partitions():
            row = [formats.get(c, "").format(part) for c in columns]
            rows.append(row)

    widths = [max(4, *map(len, col)) for col in zip(*rows)]
    fmt = " ".join("{{:{w}}}".format(w=w) for w in widths)
    for row in rows:
        print(fmt.format(*row))


def argument_parser(commands, add_global_options):
    partitions = commands.add_parser(
        "partitions",
        description="List ChromeOS kernel partitions.",
        help="List ChromeOS kernel partitions.",
        usage="%(prog)s [options] [disk ...]",
        add_help=False,
    )
    partitions_arguments = partitions.add_argument_group(
        title="Positional arguments",
    )
    partitions_arguments.add_argument(
        "disks",
        metavar="disk",
        nargs="*",
        help="Disks to check for ChromeOS kernel partitions.",
    )
    partitions_options = partitions.add_argument_group(
        title="Options",
    )
    partitions_options.add_argument(
        "-n", "--noheadings",
        dest="headings",
        action='store_false',
        help="Don't print column headings.",
    )
    partitions_options.add_argument(
        "-a", "--all-disks",
        action='store_true',
        help="List partitions on all disks.",
    )
    partitions_options.add_argument(
        "-o", "--output",
        metavar="COLUMNS",
        action='append',
        help="Comma separated list of columns to output.",
    )
    add_global_options(partitions_options)
