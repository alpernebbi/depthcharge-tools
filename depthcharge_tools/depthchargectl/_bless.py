#! /usr/bin/env python3

import argparse
import logging

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


@depthchargectl.subcommand("bless")
class depthchargectl_bless(
    depthchargectl,
    prog="depthchargectl bless",
    usage="%(prog)s [options] [PARTITION]",
    add_help=False,
):
    """Set the active or given partition as successfully booted."""

    config_section = "depthchargectl/bless"

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument(metavar="PARTITION")
    def partition(self, device=None):
        """ChromeOS Kernel partition to manage"""
        if device is None:
            try:
                device = Disk.by_kern_guid()
            except:
                raise ValueError(
                    "Couldn't figure out the currently booted partition."
                )

        return Partition(device)

    def __call__(self):
        logger.info(
            "Setting '{}' as the highest-priority bootable part."
            .format(self.partition)
        )
        self.partition.attribute = 0x111
        self.partition.prioritize()
        logger.info(
            "Set '{}' as next to boot and successful."
            .format(self.partition)
        )

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
