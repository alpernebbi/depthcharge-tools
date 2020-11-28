#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Command,
)

logger = logging.getLogger(__name__)


class DepthchargectlSetGood(Command):
    def __init__(self, name="depthchargectl set-good", parent=None):
        super().__init__(name, parent)

    def __call__(self, *args, **kwargs):
        print(args, kwargs)

    def _init_parser(self):
        return super()._init_parser(
            description="Set the current partition as successfully booted.",
            usage="%(prog)s [options]",
            add_help=False,
        )
