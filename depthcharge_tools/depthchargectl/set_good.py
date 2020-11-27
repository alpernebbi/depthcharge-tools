#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__

logger = logging.getLogger(__name__)


def _set_good(*args, **kwargs):
    print(args, kwargs)


def argument_parser(commands, add_global_options):
    set_good = commands.add_parser(
        "set-good",
        description="Set the current partition as successfully booted.",
        help="Set the current partition as successfully booted.",
        usage="%(prog)s [options]",
        add_help=False,
    )
    set_good_options = set_good.add_argument_group(
        title="Options",
    )
    add_global_options(set_good_options)

