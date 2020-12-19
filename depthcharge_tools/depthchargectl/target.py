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
        if not disks:
            disks = Disk.disks(bootable=True)

        if not disks:
            raise ValueError("no-disks")

        partitions = []
        for d in disks:
            try:
                partitions.append(Partition(d))
            except:
                partitions.extend(Disk(d).partitions())

        good_partitions = []
        for p in partitions:
            if min_size is not None and p.size < int(min_size):
                continue
            if not allow_current and p.path == Disk.by_kern_guid():
                continue
            good_partitions.append(p)

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
