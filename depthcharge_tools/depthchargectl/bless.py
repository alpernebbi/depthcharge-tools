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
class bless(
    depthchargectl,
    prog="depthchargectl bless",
    usage="%(prog)s [options]",
    add_help=False,
):
    """Set the current partition as successfully booted."""

    def __call__(self):
        try:
            part = Partition(Disk.by_kern_guid())
        except:
            raise ValueError(
                "Couldn't figure out the currently booted partition."
            )

        logger.info(
            "Setting '{}' as the highest-priority bootable part."
            .format(part)
        )
        part.attribute = 0x111
        part.prioritize()
        logger.info(
            "Set '{}' as next to boot and successful."
            .format(part)
        )

    global_options = depthchargectl.global_options
