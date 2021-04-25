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
    Partition,
    CrosPartition,
)

from depthcharge_tools.depthchargectl import depthchargectl


@depthchargectl.subcommand("bless")
class depthchargectl_bless(
    depthchargectl,
    prog="depthchargectl bless",
    usage="%(prog)s [options] [PARTITION]",
    add_help=False,
):
    """Set the active or given partition as successfully booted."""

    logger = depthchargectl.logger.getChild("bless")
    config_section = "depthchargectl/bless"

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument(metavar="PARTITION")
    def partition(self, device=None):
        """ChromeOS Kernel partition to manage"""
        if device is None:
            self.logger.info(
                "No partition given, defaulting to currently booted one."
            )
            device = system_disks.by_kern_guid()

        if device is None:
            raise ValueError(
                "Couldn't figure out the currently booted partition."
            )

        device = Partition(device)

        if device not in device.disk.cros_partitions():
            raise ValueError(
                "Partition '{}' is not a ChromeOS Kernel partition"
                .format(device)
            )

        return CrosPartition(device.path)

    @Group
    def options(self):
        """Options"""

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
            self.logger.info(
                "Setting '{}' as the highest-priority bootable part."
                .format(self.partition)
            )
            self.partition.tries = 1
            self.partition.prioritize()

            if self.oneshot == False:
                self.logger.info(
                    "Setting '{}' as successfully booted."
                    .format(self.partition)
                )
                self.partition.successful = 1

            else:
                self.logger.info(
                    "Setting '{}' as not yet successfully booted."
                    .format(self.partition)
                )
                self.partition.successful = 0

        else:
            self.logger.info(
                "Setting '{}' as the zero-priority unbootable part."
                .format(self.partition)
            )
            self.partition.attribute = 0x000

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
