#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl bless subcommand
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
from depthcharge_tools.utils.os import (
    Disk,
    Partition,
    CrosPartition,
)
from depthcharge_tools.utils.platform import (
    is_cros_boot,
)

from depthcharge_tools.depthchargectl import depthchargectl


@depthchargectl.subcommand("bless")
class depthchargectl_bless(
    depthchargectl,
    prog="depthchargectl bless",
    usage="%(prog)s [options] [DISK | PARTITION]",
    add_help=False,
):
    """Set the active or given partition as successfully booted."""

    _logger = depthchargectl._logger.getChild("bless")
    config_section = "depthchargectl/bless"

    @depthchargectl.board.copy()
    def board(self, codename=""):
        """Assume we're running on the specified board"""
        # We can bless partitions without knowing the board.
        try:
            return super().board
        except Exception as err:
            self.logger.warning(err)
            return None

    @Group
    def positionals(self):
        """Positional arguments"""
        if self.disk is not None and self.partition is not None:
            raise ValueError(
                "Disk and partition arguments are mutually exclusive."
            )

        device = self.disk or self.partition

        if isinstance(device, str):
            sys_device = self.diskinfo.evaluate(device)

            if sys_device is not None:
                self.logger.info(
                    "Using argument '{}' as a block device."
                    .format(device)
                )
                device = sys_device

            else:
                self.logger.info(
                    "Using argument '{}' as a disk image."
                    .format(device)
                )
                device = Disk(device)

        if isinstance(device, Disk):
            if self.partno is None:
                raise ValueError(
                    "Partno argument is required for disks."
                )
            partition = device.partition(self.partno)

        elif isinstance(device, Partition):
            if self.partno is not None and self.partno != device.partno:
                raise ValueError(
                    "Partition and partno arguments are mutually exclusive."
                )
            partition = device

        elif device is None:
            self.logger.info(
                "No partition given, defaulting to currently booted one."
            )
            partition = self.diskinfo.by_kern_guid()

        if partition is None:
            if is_cros_boot():
                raise ValueError(
                    "Couldn't figure out the currently booted partition."
                )
            else:
                raise ValueError(
                    "A disk or partition argument is required when not "
                    "booted with depthcharge."
                )

        self.logger.info(
            "Working on partition '{}'."
            .format(partition)
        )

        try:
            cros_partitions = partition.disk.cros_partitions()
        except subprocess.CalledProcessError as err:
            self.logger.debug(
                err,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise ValueError(
                "Couldn't get partitions for disk '{}'."
                .format(partition.disk)
            ) from err

        if partition not in cros_partitions:
            raise ValueError(
                "Partition '{}' is not a ChromeOS Kernel partition"
                .format(partition)
            )

        partition = CrosPartition(partition)
        self.partition = partition
        self.disk = partition.disk
        self.partno = partition.partno

    @positionals.add
    @Argument(nargs=0)
    def disk(self, disk=None):
        """Disk image to manage partitions of"""
        return disk

    @positionals.add
    @Argument
    def partition(self, partition=None):
        """ChromeOS Kernel partition device to manage"""
        return partition

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-i", "--partno", nargs=1)
    def partno(self, number=None):
        """Partition number in the given disk image"""
        try:
            if number is not None:
                number = int(number)
        except:
            raise TypeError(
                "Partition number must be a positive integer."
            )

        if number is not None and not number > 0:
            raise ValueError(
                "Partition number must be a positive integer."
            )

        return number

    @options.add
    @Argument("--bad", bad=True)
    def bad(self, bad=False):
        """Set the partition as unbootable"""
        return bad

    @options.add
    @Argument("--oneshot", oneshot=True)
    def oneshot(self, oneshot=False):
        """Set the partition to be tried once"""
        return oneshot

    def __call__(self):
        if self.bad == False:
            try:
                self.partition.tries = 1
            except subprocess.CalledProcessError as err:
                raise CommandExit(
                    "Failed to set remaining tries for partition '{}'."
                    .format(self.partition)
                ) from err

            if self.oneshot == False:
                try:
                    self.partition.successful = 1
                except subprocess.CalledProcessError as err:
                    raise CommandExit(
                        "Failed to set success flag for partition '{}'."
                        .format(self.partition)
                    ) from err

                self.logger.warning(
                    "Set partition '{}' as successfully booted."
                    .format(self.partition)
                )

            else:
                try:
                    self.partition.successful = 0
                except subprocess.CalledProcessError as err:
                    raise CommandExit(
                        "Failed to unset successful flag for partition '{}'."
                        .format(self.partition)
                    ) from err

                self.logger.warning(
                    "Set partition '{}' as not yet successfully booted."
                    .format(self.partition)
                )

            try:
                self.partition.prioritize()
            except subprocess.CalledProcessError as err:
                raise CommandExit(
                    "Failed to prioritize partition '{}'."
                    .format(self.partition)
                ) from err

            self.logger.info(
                "Set partition '{}' as the highest-priority bootable part."
                .format(self.partition)
            )

        else:
            try:
                self.partition.attribute = 0x000
            except subprocess.CalledProcessError as err:
                raise CommandExit(
                    "Failed to zero attributes for partition '{}'."
                    .format(self.partition)
                ) from err

            self.logger.warning(
                "Set partition '{}' as a zero-priority unbootable part."
                .format(self.partition)
            )

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
