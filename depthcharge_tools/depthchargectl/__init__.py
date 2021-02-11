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
        boards = {
            section.get("codename"): section
            for name, section in self.config.items()
            if "codename" in section
        }

        if codename is None:
            codename = self.config["depthcharge-tools"].get("board", None)

        if codename in boards:
            return codename

        elif codename is not None:
            raise ValueError(
                "Unknown board codename '{}'."
                .format(codename)
            )

        hwid = cros_hwid()
        def hwid_match(item):
            codename, section = item
            try:
                hwid_match = section.get("hwid-match")
                return bool(re.match(hwid_match, hwid))
            except:
                return False

        matches = tuple(filter(hwid_match, boards.items()))
        if matches:
            codename, section = matches[0]
            name = section.get("name", "(unnamed)")
            logger.info(
                "Detected board '{}' ('{}') by HWID."
                .format(name, codename)
            )
            return codename

        else:
            logger.warning(
                "Couldn't detect board by HWID."
            )

        compatibles = dt_compatibles()
        def compat_preference(item):
            if item is None:
                return len(compatibles)

            codename, section = item
            try:
                compat = section.get("dt-compatible", None)
                return compatibles.index(compat)
            except ValueError:
                return float("inf")

        match = min((None, *boards.items()), key=compat_preference)
        if match is not None:
            codename, section = match
            name = section.get("name", "(unnamed)")
            logger.info(
                "Detected board '{}' ('{}') by device-tree compatibles."
                .format(name, codename)
            )
            return codename

        else:
            logger.warning(
                "Couldn't detect board by dt-compatibles."
            )

        raise ValueError(
            "Could not detect which board this is running on."
        )

    @Subparsers()
    def command(self, cmd):
        """Supported subcommands"""

    def __call__(self):
        if hasattr(type(self), "list"):
            logger.info("No subcommand given, defaulting to list")
            return type(self).list()
        else:
            raise ValueError("No subcommand given")


import depthcharge_tools.depthchargectl._bless
import depthcharge_tools.depthchargectl._build
import depthcharge_tools.depthchargectl._check
import depthcharge_tools.depthchargectl._list
import depthcharge_tools.depthchargectl._remove
import depthcharge_tools.depthchargectl._target
import depthcharge_tools.depthchargectl._write

if __name__ == "__main__":
    depthchargectl._main()
