#! /usr/bin/env python3

import argparse
import configparser
import copy
import logging
import re

from depthcharge_tools import __version__, CONFIG
from depthcharge_tools.utils import (
    Command,
    Argument,
    Group,
    Subparsers,
    cros_hwid,
    dt_compatibles,
)

logger = logging.getLogger(__name__)


class depthchargectl(
    Command,
    prog="depthchargectl",
    usage="%(prog)s [options] command ...",
    add_help=False,
):
    """Manage Chrome OS kernel partitions."""

    @Group
    def global_options(self):
        """Global options"""

    @global_options.add
    @Argument("-h", "--help", action="help")
    def print_help(self):
        """Show this help message."""
        # type(self).parser.print_help()

    @global_options.add
    @Argument(
        "-V", "--version",
        action="version",
        version="depthcharge-tools %(prog)s {}".format(__version__),
    )
    def version(self):
        """Print program version."""
        return type(self).version.version % {"prog": type(self).prog}

    @global_options.add
    @Argument("-v", "--verbose", count=True)
    def verbosity(self, verbosity):
        """Print more detailed output."""
        logger = logging.getLogger()
        level = logger.getEffectiveLevel()
        level = level - int(verbosity) * 10
        logger.setLevel(level)
        return level

    @Group
    def config_options(self):
        """Config options"""

    @config_options.add
    @Argument("--config", nargs=1)
    def config(self, file_=None):
        """Override defaults with a custom configuration file"""
        parser = copy.deepcopy(CONFIG)

        if file_ is not None:
            try:
                read = parser.read([file_])

            except configparser.ParsingError as err:
                raise ValueError(
                    "Config file '{}' could not be parsed."
                    .format(err.filename)
                )

            if file_ not in read:
                raise ValueError(
                    "Config file '{}' could not be read."
                    .format(file_)
                )

        return parser

    @Group
    def board_options(self):
        """Board options"""

    @board_options.add
    @Argument("--board", nargs=1)
    def board(self, codename=None):
        """Assume we're running on the specified board"""
        if codename is None:
            codename = self.config["depthcharge-tools"].get("board", None)

        if codename is not None:
            for name, section in self.config.items():
                if codename == section.get("codename"):
                    return codename

            raise ValueError(
                "Unknown board codename '{}'."
                .format(codename)
            )

        hwid = cros_hwid()

        if hwid:
            for name, section in self.config.items():
                codename = section.get("codename")
                if not codename:
                    continue

                hwid_match = section.get("hwid-match")
                if hwid_match and re.match(hwid_match, hwid):
                    return codename

        compatibles = dt_compatibles()

        def preference(config):
            compat = config.get("dt-compatible")

            try:
                return compatibles.index(compat)
            except ValueError:
                return len(compatibles) + 1

        best_match = min(self.config.values(), key=preference)
        return best_match.get("codename")

    @Subparsers()
    def command(self, cmd):
        """Supported subcommands"""

    def __call__(self):
        if hasattr(type(self), "list"):
            logger.info("No subcommand given, defaulting to list")
            return type(self).list()
        else:
            raise ValueError("No subcommand given")


from depthcharge_tools.depthchargectl.bless import bless
from depthcharge_tools.depthchargectl.build import build
from depthcharge_tools.depthchargectl.check import check
from depthcharge_tools.depthchargectl.list import list_
from depthcharge_tools.depthchargectl.remove import remove
from depthcharge_tools.depthchargectl.target import target
from depthcharge_tools.depthchargectl.write import write

if __name__ == "__main__":
    depthchargectl._main()
