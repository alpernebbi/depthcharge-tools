#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl list subcommand
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import argparse
import logging
import subprocess

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
    CommandExit,
)
from depthcharge_tools.utils.collections import (
    TypedList
)
from depthcharge_tools.utils.os import (
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

    _logger = depthchargectl._logger.getChild("list")
    config_section = "depthchargectl/list"

    @depthchargectl.board.copy()
    def board(self, codename=""):
        """Assume we're running on the specified board"""
        # We can list partitions without knowing the board.
        try:
            return super().board
        except Exception as err:
            self.logger.warning(err)
            return None

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument(metavar="DISK")
    def disks(self, *disks):
        """Disks to check for ChromeOS kernel partitions."""

        if self.all_disks:
            self.logger.info("Searching all disks.")
            disks = self.diskinfo.roots()
        elif disks:
            self.logger.info(
                "Searching real disks for {}."
                .format(", ".join(str(d) for d in disks))
            )
            images = []
            for d in disks:
                if self.diskinfo.evaluate(d) is None:
                    try:
                        images.append(Disk(d))
                    except ValueError as err:
                        self.logger.warning(
                            err,
                            exc_info=self.logger.isEnabledFor(logging.DEBUG),
                        )
            disks = [*self.diskinfo.roots(*disks), *images]
        else:
            self.logger.info("Searching bootable disks.")
            root = (
                self.diskinfo.by_mountpoint("/", fstab_only=True)
                or self.diskinfo.by_mountpoint(self.root_mountpoint)
            )
            boot = (
                self.diskinfo.by_mountpoint("/boot", fstab_only=True)
                or self.diskinfo.by_mountpoint(self.boot_mountpoint)
            )
            disks = self.diskinfo.roots(root, boot)

        if disks:
            self.logger.info(
                "Using disks: {}."
                .format(", ".join(str(d) for d in disks))
            )
        else:
            raise ValueError("Could not find any matching disks.")

        return disks

    @Group
    def options(self):
        """Options"""
        if self.count and self.output:
            raise ValueError(
                "Count and Output arguments are mutually exclusive."
            )

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

    @options.add
    @Argument("-c", "--count", count=True)
    def count(self, count=False):
        """Print only the count of partitions."""
        return count

    def __call__(self):
        parts = []
        error_disks = []

        for disk in self.disks:
            try:
                parts.extend(disk.cros_partitions())
            except subprocess.CalledProcessError as err:
                error_disks.append(disk)
                self.logger.debug(
                    "Couldn't get partitions for disk '{}'."
                    .format(disk)
                )
                self.logger.debug(
                    err,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG),
                )

        if self.count:
            output = len(parts)

        else:
            output = CrosPartitions(
                parts,
                headings=self.headings,
                columns=self.output,
            )

        if error_disks:
            return CommandExit(
                message=(
                    "Couldn't get partitions for disks {}."
                    .format(", ".join(str(d) for d in error_disks))
                ),
                output=output,
                returncode=1,
            )

        return output

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options

