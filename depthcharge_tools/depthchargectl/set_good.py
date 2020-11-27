#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__

logger = logging.getLogger(__name__)


def _set_good(*args, **kwargs):
    print(args, kwargs)


def argument_parser(parent, add_global_options):
    parser = parent.add_parser(
        "set-good",
        description="Set the current partition as successfully booted.",
        help="Set the current partition as successfully booted.",
        usage="%(prog)s [options]",
        add_help=False,
    )

    options = parser.add_argument_group(
        title="Options",
    )
    add_global_options(options)

    return parser
