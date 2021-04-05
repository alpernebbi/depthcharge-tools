#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
)
from depthcharge_tools.utils.collections import (
    TypedList
)
from depthcharge_tools.utils.os import (
    system_disks,
    Disk,
    CrosPartition,
)

from depthcharge_tools.depthchargectl import depthchargectl


class CrosPartitions(TypedList(CrosPartition)):
    def __init__(self, partitions=None, columns=None, headings=True):
        super().__init__(partitions)

        if columns is None:
            if any(part.path is None for part in partitions):
                columns = ["S", "P", "T", "DISKPATH", "PARTNO"]
            else:
                columns = ["S", "P", "T", "PATH"]

        self._headings = headings
        self._columns = columns

    def _row(self, part):
        values = {}

        if set(self._columns).intersection((
            "A", "S", "P", "T",
            "ATTRIBUTE", "SUCCESSFUL", "PRIORITY", "TRIES",
        )):
            flags = part.flags
            values.update({
                "A": flags["attribute"],
                "S": flags["successful"],
                "P": flags["priority"],
                "T": flags["tries"],
                "ATTRIBUTE": flags["attribute"],
                "SUCCESSFUL": flags["successful"],
                "PRIORITY": flags["priority"],
                "TRIES": flags["tries"],
            })

        if "SIZE" in self._columns:
            values["SIZE"] = part.size

        if part.path is not None:
            values["PATH"] = part.path

        if part.disk is not None and part.disk.path is not None:
            values["DISK"] = part.disk.path
            values["DISKPATH"] = part.disk.path

        if part.partno is not None:
            values["PARTNO"] = part.partno

        return [str(values.get(c, "")) for c in self._columns]

    def __str__(self):
        rows = []

        if self._headings:
            rows.append(self._columns)

        parts = sorted(self, key=lambda p: p.path or p.disk.path)
        rows.extend(self._row(part) for part in parts)

        # Using tab characters makes things misalign when the data
        # widths vary, so find max width for each column from its data,
        # and format everything to those widths.
        widths = [max(4, *map(len, col)) for col in zip(*rows)]
        fmt = " ".join("{{:{w}}}".format(w=w) for w in widths)
        return "\n".join(fmt.format(*row) for row in rows)


@depthchargectl.subcommand("list")
class depthchargectl_list(
    depthchargectl,
    prog="depthchargectl list",
    usage="%(prog)s [options] [DISK ...]",
    add_help=False,
):
    """List ChromeOS kernel partitions."""

    logger = depthchargectl.logger.getChild("list")
    config_section = "depthchargectl/list"

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument(metavar="DISK")
    def disks(self, *disks):
        """Disks to check for ChromeOS kernel partitions."""

        if self.all_disks:
            self.logger.info("Searching all disks.")
            disks = system_disks.roots()
        elif disks:
            self.logger.info("Searching real disks for {}.".format(disks))
            images = [
                Disk(d)
                for d in disks
                if system_disks.evaluate(d) is None
            ]
            disks = [*system_disks.roots(*disks), *images]
        else:
            self.logger.info("Searching bootable disks.")
            disks = system_disks.bootable_disks()

        if disks:
            self.logger.info("Using disks: {}.".format(disks))
        else:
            raise ValueError("Could not find any matching disks.")

        return disks

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-n", "--noheadings", headings=False)
    def headings(self, headings=True):
        """Don't print column headings."""
        return headings

    @options.add
    @Argument("-a", "--all-disks", all_disks=True)
    def all_disks(self, all_disks=False):
        """List partitions on all disks."""
        return all_disks

    valid_columns = {
        "ATTRIBUTE", "SUCCESSFUL", "PRIORITY", "TRIES",
        "A", "S", "P", "T",
        "PATH",
        "DISKPATH", "DISK",
        "PARTNO",
        "SIZE",
    }

    @options.add
    @Argument("-o", "--output", nargs=1, append=True)
    def output(self, *columns):
        """Comma separated list of columns to output."""

        if len(columns) == 0:
            self.logger.info("Using default output format.")
            return None

        elif len(columns) == 1 and isinstance(columns[0], str):
            columns = columns[0]
            self.logger.info("Using output format '{}'.".format(columns))

        else:
            columns = ",".join(columns)
            self.logger.info("Using output format '{}'.".format(columns))

        columns = columns.split(',')

        invalid_columns = sorted(
            set(columns).difference(self.valid_columns),
            key=columns.index,
        )
        if invalid_columns:
            raise ValueError(
                "Unsupported output columns '{}'."
                .format(invalid_columns)
            )

        return columns

    def __call__(self):
        parts = []
        for disk in self.disks:
            parts.extend(disk.cros_partitions())

        return CrosPartitions(
            parts,
            headings=self.headings,
            columns=self.output,
        )

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options

