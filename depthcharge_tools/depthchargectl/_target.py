#! /usr/bin/env python3

import argparse
import logging
import sys
import types

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
    Command,
    Argument,
    Group,
)


from depthcharge_tools.depthchargectl import depthchargectl

logger = logging.getLogger(__name__)


@depthchargectl.subcommand("target")
class depthchargectl_target(
    depthchargectl,
    prog="depthchargectl target",
    usage="%(prog)s [options] [PARTITION | DISK ...]",
    add_help=False,
):
    """Choose or validate a ChromeOS Kernel partition to use."""

    config_section = "depthchargectl/target"

    @Group
    def positionals(self):
        """Positional arguments"""

        disks = list(self.disks)
        partitions = list(self.partitions)

        # Disks containing /boot and / should be available during boot,
        # so we target only them by default.
        if not disks:
            disks = Disk.disks(bootable=True)

        if not disks:
            raise ValueError(
                "Couldn't find a real disk containing root or boot."
            )

        # The inputs can be a mixed list of partitions and disks,
        # separate the two.
        for d in list(disks):
            try:
                partitions.append(Partition(d))
                logger.info("Using target '{}' as a partition.".format(d))
                disks.remove(d)
            except:
                pass

        # For arguments which are disks, search all their partitions.
        if disks:
            logger.info("Finding disks for targets '{}'.".format(disks))
            for d in Disk.disks(*disks):
                logger.info("Using '{}' as a disk.".format(d))
                partitions.extend(d.partitions())

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
            return int(min_size)

    @options.add
    @Argument("--allow-current", allow=True)
    def allow_current(self, allow=False):
        """Allow targeting the currently booted partition."""
        return allow

    def __call__(self):
        # We will need to check partitions against this if allow_current
        # is false.
        current = Disk.by_kern_guid()

        # Given a single partition, check if the partition is valid.
        if len(self.partitions) == 1 and len(self.disks) == 0:
            part = self.partitions[0]

            logger.info("Checking if target partition is writable.")
            if part.path is not None and not part.path.is_block_device():
                raise OSError(
                    2,
                    "Target '{}' is not a valid block device."
                    .format(part),
                )

            logger.info("Checking if targeted partition's disk is writable.")
            if not part.disk.path.is_block_device():
                raise OSError(
                    3,
                    "Target '{}' is not a valid block device."
                    .format(part),
                )

            logger.info(
                "Checking if we can parse targeted partition's "
                "partition number."
            )
            if part.partno is None:
                raise OSError(
                    4,
                    "Could not parse partition number for '{}'."
                    .format(part),
                )

            logger.info(
                "Checking if targeted partition's type is Chrome OS Kernel."
            )
            if part.partno not in (p.partno for p in part.disk.partitions()):
                raise OSError(
                    5,
                    "Partition '{}' is not of type Chrome OS Kernel."
                    .format(part),
                )

            logger.info(
                "Checking if targeted partition is currently booted one."
            )
            if not self.allow_current and part.path == current:
                raise OSError(
                    6,
                    "Partition '{}' is the currently booted parttiion."
                    .format(part),
                )

            logger.info(
                "Checking if targeted partition is bigger than given "
                "minimum size."
            )
            if self.min_size is not None and part.size < self.min_size:
                raise OSError(
                    7,
                    "Partition '{}' smaller than '{}' bytes."
                    .format(part, self.min_size),
                )

        good_partitions = []
        for p in self.partitions:
            if self.min_size is not None and p.size < self.min_size:
                logger.info(
                    "Skipping partition '{}' as too small."
                    .format(p)
                )
                continue

            if not self.allow_current and p.path == current:
                logger.info(
                    "Skipping currently booted partition '{}'."
                    .format(p)
                )
                continue

            logger.info("Partition '{}' is usable.".format(p))
            good_partitions.append(p)

        # Get the least-successful, least-priority, least-tries-left
        # partition in that order of preference.
        good_partitions = sorted(
            good_partitions,
            key=lambda p: (p.successful, p.priority, p.tries, p.size),
        )

        if good_partitions:
            return good_partitions[0]
        else:
            raise ValueError(
                "No usable Chrome OS Kernel partition found "
                "for given input arguments."
            )

    global_options = depthchargectl.global_options


