#! /usr/bin/env python3

import argparse
import logging
import sys
import types

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
)
from depthcharge_tools.utils import OldCommand as Command

logger = logging.getLogger(__name__)


class DepthchargectlTarget(Command):
    def __init__(self, name="depthchargectl target", parent=None):
        super().__init__(name, parent)

    def __call__(
        self,
        disks=None,
        min_size=None,
        allow_current=False,
    ):
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
        partitions = []
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

        # We will need to check partitions against this if allow_current
        # is false.
        current = Disk.by_kern_guid()

        # Given a single partition, check if the partition is valid.
        if len(partitions) == 1 and len(disks) == 0:
            part = partitions[0]

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
            if not allow_current and part.path == current:
                raise OSError(
                    6,
                    "Partition '{}' is the currently booted parttiion."
                    .format(part),
                )

            logger.info(
                "Checking if targeted partition is bigger than given "
                "minimum size."
            )
            if min_size is not None and part.size < int(min_size):
                raise OSError(
                    7,
                    "Partition '{}' smaller than '{}' bytes."
                    .format(part, min_size),
                )

        good_partitions = []
        for p in partitions:
            if min_size is not None and p.size < int(min_size):
                logger.info(
                    "Skipping partition '{}' as too small."
                    .format(p)
                )
                continue

            if not allow_current and p.path == current:
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

    def _init_parser(self):
        return super()._init_parser(
            description="Choose or validate a ChromeOS Kernel partition to use.",
            usage="%(prog)s [options] [partition | disk ...]",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            "partition",
            nargs=argparse.SUPPRESS,
            default=argparse.SUPPRESS,
            help="Chrome OS kernel partition to validate.",
        )
        arguments.add_argument(
            "disks",
            nargs="*",
            help="Disks to search for an appropriate Chrome OS kernel partition.",
        )

    def _init_options(self, options):
        options.add_argument(
            "-s", "--min-size",
            metavar="BYTES",
            action='store',
            help="Target partitions larger than this size.",
        )
        options.add_argument(
            "--allow-current",
            action='store_true',
            help="Allow targeting the currently booted partition.",
        )
