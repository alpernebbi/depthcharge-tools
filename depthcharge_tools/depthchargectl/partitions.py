#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import Disk
from depthcharge_tools.utils import OldCommand as Command

logger = logging.getLogger(__name__)


class DepthchargectlPartitions(Command):
    def __init__(self, name="depthchargectl partitions", parent=None):
        super().__init__(name, parent)

    def __call__(
        self,
        disks=None,
        headings=True,
        all_disks=False,
        output=None,
    ):
        if all_disks:
            logger.info("Searching all disks.")
            disks = Disk.disks()
        elif disks:
            logger.info("Searching real disks for {}.".format(disks))
            disks = Disk.disks(*disks)
        else:
            logger.info("Searching bootable disks.")
            disks = Disk.disks(bootable=True)

        if disks:
            logger.info("Using disks: {}.".format(disks))
        else:
            raise ValueError("Could not find any matching disks.")

        if output is None:
            output = "S,P,T,PATH"
            logger.info("Using default output format '{}'.".format(output))
        elif isinstance(output, list):
            output = ",".join(output)
            logger.info("Using output format '{}'.".format(output))

        # This is just trying to getattr things, but getting DISKPATH is
        # easier this way.
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

        for c in columns:
            if c not in formats:
                raise ValueError(
                    "Unsupported output column '{}'."
                    .format(c)
                )

        if headings:
            logger.info("Including headings.")
            rows.append(list(columns))

        # Get the actual table data we want to print
        for disk in disks:
            for part in disk.partitions():
                row = [formats.get(c, "").format(part) for c in columns]
                rows.append(row)

        # Using tab characters makes things misalign when the data
        # widths vary, so find max width for each column from its data,
        # and format everything to those widths.
        widths = [max(4, *map(len, col)) for col in zip(*rows)]
        fmt = " ".join("{{:{w}}}".format(w=w) for w in widths)
        return "\n".join(fmt.format(*row) for row in rows)

    def _init_parser(self):
        return super()._init_parser(
            description="List ChromeOS kernel partitions.",
            usage="%(prog)s [options] [disk ...]",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            "disks",
            metavar="disk",
            nargs="*",
            help="Disks to check for ChromeOS kernel partitions.",
        )

    def _init_options(self, options):
        options.add_argument(
            "-n", "--noheadings",
            dest="headings",
            action='store_false',
            help="Don't print column headings.",
        )
        options.add_argument(
            "-a", "--all-disks",
            action='store_true',
            help="List partitions on all disks.",
        )
        options.add_argument(
            "-o", "--output",
            metavar="COLUMNS",
            action='append',
            help="Comma separated list of columns to output.",
        )
