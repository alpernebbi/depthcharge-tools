#! /usr/bin/env python3

import argparse
import logging
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
    system_disks,
    Disk,
    CrosPartition,
    Partition,
)

from depthcharge_tools.depthchargectl import depthchargectl


class NotABlockDeviceError(CommandExit):
    def __init__(self, device):
        message = (
            "Target '{}' is not a valid block device."
            .format(device)
        )

        self.device = device
        super().__init__(message=message)


class NotCrosPartitionError(CommandExit):
    def __init__(self, partition):
        message = (
            "Partition '{}' is not of type Chrome OS Kernel."
            .format(partition)
        )

        self.partition = partition
        super().__init__(message=message)


class BootedPartitionError(CommandExit):
    def __init__(self, partition):
        message = (
            "Partition '{}' is the currently booted parttiion."
            .format(partition)
        )

        self.partition = partition
        super().__init__(message=message)


class PartitionSizeTooSmallError(CommandExit):
    def __init__(self, partition, part_size, min_size):
        message = (
            "Partition '{}' ('{}' bytes) is smaller than '{}' bytes."
            .format(partition, part_size, min_size)
        )

        self.partition = partition
        self.part_size = part_size
        self.min_size = min_size
        super().__init__(message=message)


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

    logger = depthchargectl.logger.getChild("target")
    config_section = "depthchargectl/target"

    @Group
    def positionals(self):
        """Positional arguments"""

        disks = list(self.disks)
        partitions = list(self.partitions)

        # Disks containing /boot and / should be available during boot,
        # so we target only them by default.
        if not disks:
            disks = system_disks.bootable_disks()

        if not disks:
            raise ValueError(
                "Couldn't find a real disk containing root or boot."
            )

        # The inputs can be a mixed list of partitions and disks,
        # separate the two.
        for d in list(disks):
            try:
                partitions.append(Partition(d))
                self.logger.info("Using target '{}' as a partition.".format(d))
                disks.remove(d)
            except:
                pass

        # For arguments which are disks, search all their partitions.
        if disks:
            self.logger.info("Finding disks for targets '{}'.".format(disks))
            images = [
                Disk(d)
                for d in disks
                if system_disks.evaluate(d) is None
            ]

            for d in (*system_disks.roots(*disks), *images):
                self.logger.info("Using '{}' as a disk.".format(d))
                partitions.extend(d.cros_partitions())

        self.disks = disks
        self.partitions = partitions

    @positionals.add
    @Argument(metavar="PARTITION", nargs=argparse.SUPPRESS)
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
    @Argument("-s", "--min-size")
    def min_size(self, bytes_):
        """Target partitions larger than this size."""
        if bytes_ is None:
            return None
        elif isinstance(bytes_, int):
            return bytes_
        elif bytes_.startswith("0x"):
            return int(bytes_, 16)
        elif bytes_.startswith("0o"):
            return int(bytes_, 8)
        elif bytes_.startswith("0b"):
            return int(bytes_, 2)
        else:
            return int(bytes_)

    @options.add
    @Argument("--allow-current", allow=True)
    def allow_current(self, allow=False):
        """Allow targeting the currently booted partition."""
        return allow

    def __call__(self):
        # We will need to check partitions against this if allow_current
        # is false.
        current = system_disks.by_kern_guid()

        # Given a single partition, check if the partition is valid.
        if len(self.partitions) == 1 and len(self.disks) == 0:
            part = self.partitions[0]

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

        good_partitions = []
        for p in self.partitions:
            if self.min_size is not None and p.size < self.min_size:
                self.logger.info(
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


