#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
    CommandExit,
)

from depthcharge_tools.depthchargectl import depthchargectl


@depthchargectl.subcommand("config")
class depthchargectl_config(
    depthchargectl,
    prog="depthchargectl config",
    usage="%(prog)s [options] KEY",
    add_help=False,
):
    """Get depthchargectl configuration values."""

    logger = depthchargectl.logger.getChild("config")
    config_section = "depthchargectl/config"

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument
    def key(self, key):
        """Config key to get value of."""
        return key

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("--section", nargs=1)
    def section(self, section=None):
        """Config section to work on."""
        parser = self.config.parser

        if section is None:
            section = parser.default_section

        if section not in parser.sections():
            if section != parser.default_section:
                parser.add_section(section)

        return parser[section]

    @options.add
    @Argument("--default", nargs=1)
    def default(self, default=None):
        """Value to return if key doesn't exist in section."""
        return default

    def __call__(self):
        if self.key not in self.section:
            if self.default is not None:
                return self.default
            else:
                raise KeyError(
                    "Key '{}' not found in section '{}'."
                    .format(self.key, self.section.name)
                )

        return self.section[self.key]

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
