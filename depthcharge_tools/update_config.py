#! /usr/bin/env python3

import logging

from pathlib import Path

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
)

class update_config(
    Command,
    prog="update_config.py",
    add_help=False,
):
    """Maintainer tool to help update depthcharge-tools config.ini"""

    logger = logging.getLogger(__name__)

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-h", "--help", action="help")
    def print_help(self):
        """Show this help message."""
        # type(self).parser.print_help()

    @options.add
    @Argument(
        "-V", "--version",
        action="version",
        version="depthcharge-tools %(prog)s {}".format(__version__),
    )
    def version(self):
        """Print program version."""
        return type(self).version.version % {"prog": type(self).prog}

    @options.add
    @Argument("-v", "--verbose", count=True)
    def verbosity(self, verbosity=0):
        """Print more detailed output."""
        level = logging.WARNING - int(verbosity) * 10
        self.logger.setLevel(level)
        return verbosity

    def __call__(self):
        pass


if __name__ == "__main__":
    update_config.main()
