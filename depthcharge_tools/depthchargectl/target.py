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
)

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

        good_partitions = []
        for p in partitions:
            if min_size is not None and p.size < int(min_size):
                logger.info(
                    "Skipping partition '{}' as too small."
                    .format(p)
                )
                continue

            if not allow_current and p.path == Disk.by_kern_guid():
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
