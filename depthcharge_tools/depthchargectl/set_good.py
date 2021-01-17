#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
)
from depthcharge_tools.utils import OldCommand as Command

logger = logging.getLogger(__name__)


class DepthchargectlSetGood(Command):
    def __init__(self, name="depthchargectl set-good", parent=None):
        super().__init__(name, parent)

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

    def _init_parser(self):
        return super()._init_parser(
            description="Set the current partition as successfully booted.",
            usage="%(prog)s [options]",
            add_help=False,
        )
