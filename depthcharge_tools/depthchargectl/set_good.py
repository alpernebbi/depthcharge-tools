#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
    Command,
)

logger = logging.getLogger(__name__)


class DepthchargectlSetGood(Command):
    def __init__(self, name="depthchargectl set-good", parent=None):
        super().__init__(name, parent)

    def __call__(self):
        part = Partition(Disk.by_kern_guid())
        part.attribute = 0x111
        part.prioritize()

    def _init_parser(self):
        return super()._init_parser(
            description="Set the current partition as successfully booted.",
            usage="%(prog)s [options]",
            add_help=False,
        )
