#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl target subcommand
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import argparse
import logging
import subprocess
import sys
import types

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
    CommandExit,
)
from depthcharge_tools.utils.os import (
    Disk,
    CrosPartition,
    Partition,
)
from depthcharge_tools.utils.string import (
    parse_bytesize,
)

from depthcharge_tools.depthchargectl import depthchargectl


class NotABlockDeviceError(CommandExit):
    def __init__(self, device):
        message = (
            "Target '{}' is not a valid block device."
            .format(device)
        )

        self.device = device
        super().__init__(message=message, returncode=2)


class NotCrosPartitionError(CommandExit):
    def __init__(self, partition):
        message = (
            "Partition '{}' is not of type Chrome OS Kernel."
            .format(partition)
        )

        self.partition = partition
        super().__init__(message=message, returncode=5)


class BootedPartitionError(CommandExit):
    def __init__(self, partition):
        message = (
            "Partition '{}' is the currently booted parttiion."
            .format(partition)
        )

        self.partition = partition
        super().__init__(message=message, returncode=6)


class PartitionSizeTooSmallError(CommandExit):
    def __init__(self, partition, part_size, min_size):
        message = (
            "Partition '{}' ('{}' bytes) is smaller than '{}' bytes."
            .format(partition, part_size, min_size)
        )

        self.partition = partition
        self.part_size = part_size
        self.min_size = min_size
        super().__init__(message=message, returncode=7)


class NoUsableCrosPartition(CommandExit):
    def __init__(self):
        message = (
            "No usable Chrome OS Kernel partition found "
            "for given input arguments."
        )

        super().__init__(message=message, output=None)


@depthchargectl.subcommand("target")
class depthchargectl_target(
    depthchargectl,
    prog="depthchargectl target",
    usage="%(prog)s [options] [PARTITION | DISK ...]",
    add_help=False,
):
    """Choose or validate a ChromeOS Kernel partition to use."""

    _logger = depthchargectl._logger.getChild("target")
    config_section = "depthchargectl/target"

    @depthchargectl.board.copy()
    def board(self, codename=""):
        """Assume we're running on the specified board"""
        # We can target partitions without knowing the board.
        try:
            return super().board
        except Exception as err:
            self.logger.warning(err)
            return None

    @Group
    def positionals(self):
        """Positional arguments"""

        disks = list(self.disks)
        partitions = list(self.partitions)

        # The inputs can be a mixed list of partitions and disks,
        # separate the two.
        for d in list(disks):
            try:
                partitions.append(Partition(d))
                self.logger.info("Using target '{}' as a partition.".format(d))
                disks.remove(d)
            except:
                pass

        self.disks = disks
        self.partitions = partitions

    @positionals.add
    @Argument(metavar="PARTITION", nargs=0)
    def partitions(self, *partitions):
        """Chrome OS kernel partition to validate."""
        return partitions

    @positionals.add
    @Argument(metavar="DISK")
    def disks(self, *disks):
        """Disks to search for an appropriate Chrome OS kernel partition."""
        return disks

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-s", "--min-size", nargs=1)
    def min_size(self, bytes_=None):
        """Target partitions larger than this size."""
        if bytes_ is None:
            return 0x10000

        return parse_bytesize(bytes_)

    @options.add
    @Argument("--allow-current", allow=True)
    def allow_current(self, allow=False):
        """Allow targeting the currently booted partition."""
        return allow

    @options.add
    @Argument("-a", "--all-disks", all_disks=True)
    def all_disks(self, all_disks=False):
        """Target partitions on all disks."""
        return all_disks

    def __call__(self):
        disks = list(self.disks)
        partitions = list(self.partitions)

        # We will need to check partitions against this if allow_current
        # is false.
        current = self.diskinfo.by_kern_guid()

        # Given a single partition, check if the partition is valid.
        if len(partitions) == 1 and len(disks) == 0:
            part = partitions[0]

            self.logger.info("Checking if target partition is writable.")
            if part.path is not None and not part.path.is_block_device():
                raise NotABlockDeviceError(part.path)

            self.logger.info("Checking if targeted partition's disk is writable.")
            if not part.disk.path.is_block_device():
                raise NotABlockDeviceError(part.disk.path)

            self.logger.info(
                "Checking if targeted partition's type is Chrome OS Kernel."
            )
            if part not in part.disk.cros_partitions():
                raise NotCrosPartitionError(part)

            self.logger.info(
                "Checking if targeted partition is currently booted one."
            )
            if current is not None and not self.allow_current:
                if part.path == current.path:
                    raise BootedPartitionError(part)

            self.logger.info(
                "Checking if targeted partition is bigger than given "
                "minimum size."
            )
            if self.min_size is not None and part.size < self.min_size:
                raise PartitionSizeTooSmallError(
                    part,
                    part.size,
                    self.min_size,
                )

        # For arguments which are disks, search all their partitions.
        # If no disks or partitions were given, search bootable disks.
        # Search all disks if explicitly asked.
        if disks or not partitions or self.all_disks:
            partitions += depthchargectl.list(
                disks=disks,
                all_disks=self.all_disks,
                root=self.root,
                root_mountpoint=self.root_mountpoint,
                boot_mountpoint=self.boot_mountpoint,
                config=self.config,
                board=self.board,
                tmpdir=self.tmpdir / "list",
                images_dir=self.images_dir,
                vboot_keyblock=self.vboot_keyblock,
                vboot_public_key=self.vboot_public_key,
                vboot_private_key=self.vboot_private_key,
                kernel_cmdline=self.kernel_cmdline,
                ignore_initramfs=self.ignore_initramfs,
                verbosity=self.verbosity,
            )

        good_partitions = []
        for p in partitions:
            if self.min_size is not None and p.size < self.min_size:
                self.logger.warning(
                    "Skipping partition '{}' as too small."
                    .format(p)
                )
                continue

            if current is not None and not self.allow_current:
                if p.path == current.path:
                    self.logger.info(
                        "Skipping currently booted partition '{}'."
                        .format(p)
                    )
                    continue

            self.logger.info("Partition '{}' is usable.".format(p))
            good_partitions.append(
                CrosPartition(p.disk.path, partno=p.partno),
            )

        # Get the least-successful, least-priority, least-tries-left
        # partition in that order of preference.
        if good_partitions:
            return min(good_partitions)
        else:
            return NoUsableCrosPartition()

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options


