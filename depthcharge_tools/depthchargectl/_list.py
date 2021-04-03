#! /usr/bin/env python3

import argparse
import collections
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
)
from depthcharge_tools.utils.os import (
    system_disks,
    Disk,
    CrosPartition,
)

from depthcharge_tools.depthchargectl import depthchargectl


class CrosPartitions(collections.UserList):
    # This is just trying to getattr things, but getting DISKPATH is
    # easier this way.
    _formats = {
            "ATTRIBUTE": "{0.attribute}",
            "SUCCESSFUL": "{0.successful}",
            "PRIORITY": "{0.priority}",
            "TRIES": "{0.tries}",
            "A": "{0.attribute}",
            "S": "{0.successful}",
            "P": "{0.priority}",
            "T": "{0.tries}",
            "PATH": "{0.path}",
            "DISKPATH": "{0.disk.path}",
            "PARTNO": "{0.partno}",
            "SIZE": "{0.size}",
    }

    def __init__(self, partitions=None, columns=None, headings=True):
        if partitions is None:
            partitions = []

        for part in partitions:
            self._check(part)

        if columns is None:
            columns = ["S", "P", "T", "PATH"]

        self._headings = headings
        self._columns = columns
        super().__init__(partitions)

    def _check(self, *args):
        if not all(isinstance(arg, CrosPartition) for arg in args):
            raise TypeError(
                "CrosPartitions items must be CrosPartition objects."
            )

    def __setitem__(self, idx, value):
        self._check(value)
        return super().__setitem__(idx, value)

    def __iadd__(self, other):
        self._check(*other)
        return super().__iadd__(other)

    def append(self, value):
        self._check(value)
        return super().append(value)

    def insert(self, idx, value):
        self._check(value)
        return super().insert(idx, value)

    def extend(self, other):
        self._check(*other)
        return super().extend(other)

    def __str__(self):
        rows = []

        if self._headings:
            rows.append(self._columns)

        # Get the actual table data we want to print
        for part in self:
            rows.append([
                self._formats.get(c, "").format(part)
                for c in self._columns
            ])

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

        for c in columns:
            if c not in CrosPartitions._formats:
                raise ValueError(
                    "Unsupported output column '{}'."
                    .format(c)
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

