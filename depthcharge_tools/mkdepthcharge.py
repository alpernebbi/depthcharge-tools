#! /usr/bin/env python3

from depthcharge_tools import __version__

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def main(*argv):
    args = parse_args(*argv)


def parse_args(*argv):
    parser = argparse.ArgumentParser(
        description="Build boot images for the ChromeOS firmware.",
        add_help=True,
    )

    parser.add_argument(
        "--version",
        action='version',
        version="%(prog)s {}".format(__version__),
        help="print version information and exit",
    )

    return parser.parse_args(*argv[1:])


if __name__ == "__main__":
    main(sys.argv)
