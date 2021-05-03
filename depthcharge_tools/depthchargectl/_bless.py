#! /usr/bin/env python3

import argparse
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

    logger = depthchargectl.logger.getChild("bless")
    config_section = "depthchargectl/bless"

    @Group
    def positionals(self):
        """Positional arguments"""
        if self.disk is not None and self.partition is not None:
            raise ValueError(
                "Disk and partition arguments are mutually exclusive."
            )

        device = self.disk or self.partition

        if isinstance(device, str):
            sys_device = system_disks[device]

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
            partition = system_disks.by_kern_guid()

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

        if partition not in partition.disk.cros_partitions():
            raise ValueError(
                "Partition '{}' is not a ChromeOS Kernel partition"
                .format(partition)
            )

        partition = CrosPartition(partition)
        self.partition = partition
        self.disk = partition.disk
        self.partno = partition.partno

    @positionals.add
    @Argument(nargs=argparse.SUPPRESS)
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
            self.partition.tries = 1
            self.partition.prioritize()
            self.logger.info(
                "Set partition '{}' as the highest-priority bootable part."
                .format(self.partition)
            )

            if self.oneshot == False:
                self.partition.successful = 1
                self.logger.warn(
                    "Set partition '{}' as successfully booted."
                    .format(self.partition)
                )

            else:
                self.partition.successful = 0
                self.logger.warn(
                    "Set partition '{}' as not yet successfully booted."
                    .format(self.partition)
                )

        else:
            self.partition.attribute = 0x000
            self.logger.warn(
                "Set partition '{}' as the zero-priority unbootable part."
                .format(self.partition)
            )

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
