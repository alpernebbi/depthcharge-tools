#! /usr/bin/env python3

import argparse
import configparser
import copy
import glob
import logging
import os
import re
import tempfile

from depthcharge_tools import __version__, config_ini, config_files
from depthcharge_tools.utils import (
    Command,
    Argument,
    Group,
    Subparsers,
    ConfigDict,
    Path,
    vboot_keys,
    cros_hwid,
    dt_compatibles,
)

logger = logging.getLogger(__name__)


class Board:
    def __init__(self, config):
        self._config = config

    @property
    def name(self):
        return self._config.get("name")

    @property
    def codename(self):
        return self._config.get("codename")

    @property
    def dt_compatible(self):
        compat = self._config.get("dt-compatible", "False")
        if compat == "True":
            return True
        elif compat == "False":
            return False
        else:
            return compat

    @property
    def hwid_match(self):
        pattern = self._config.get("hwid-match")
        if pattern:
            return re.compile(pattern)

    @property
    def boots_lz4_kernel(self):
        return self._config.getboolean("boots-lz4-kernel", False)

    @property
    def boots_lzma_kernel(self):
        return self._config.getboolean("boots-lzma-kernel", False)

    @property
    def image_max_size(self):
        return self._config.getint("image-max-size")

    @property
    def image_format(self):
        return self._config.get("image-format")


class depthchargectl(
    Command,
    prog="depthchargectl",
    usage="%(prog)s [options] command ...",
    add_help=False,
):
    """Manage Chrome OS kernel partitions."""

    config_section = "depthchargectl"

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

    @global_options.add
    @Argument("--tmpdir", nargs=1)
    def tmpdir(self, dir_=None):
        """Directory to keep temporary files."""
        if dir_ is None:
            dir_ = tempfile.TemporaryDirectory(
                prefix="depthchargectl-",
            )
            dir_ = self.exitstack.enter_context(dir_)

        dir_ = Path(dir_)
        os.makedirs(dir_, exist_ok=True)

        logger.debug("Working in temp dir '{}'.".format(dir_))

        return dir_

    @Group
    def config_options(self):
        """Configuration options"""

        # Autodetect OS-distributed keys if custom values not given.
        keydir, keyblock, signprivate, signpubkey = vboot_keys()
        if self.vboot_keyblock is None:
            self.vboot_keyblock = keyblock
        if self.vboot_private_key is None:
            self.vboot_private_key = signprivate
        if self.vboot_public_key is None:
            self.vboot_public_key = signpubkey

    @config_options.add
    @Argument("--config", nargs=1)
    def config(self, file_=None):
        """Additional configuration file to read"""
        parser = configparser.ConfigParser(
            default_section="depthcharge-tools",
            dict_type=ConfigDict,
        )

        parser.read_string(config_ini, source="config.ini")

        try:
            for p in parser.read(config_files):
                logger.debug("Read config file '{}'.".format(p))

        except configparser.ParsingError as err:
            logger.warning(
                "Config file '{}' could not be parsed."
                .format(err.filename)
            )

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

        if self.config_section not in parser.sections():
            parser.add_section(self.config_section)

        return parser[self.config_section]

    @config_options.add
    @Argument("--board", nargs=1)
    def board(self, codename=None):
        """Assume we're running on the specified board"""
        boards = {
            section.get("codename"): Board(section)
            for name, section in self.config.parser.items()
            if "codename" in section
        }

        if codename is None:
            codename = self.config.get("board", None)

        if codename in boards:
            return boards[codename]

        elif codename is not None:
            raise ValueError(
                "Unknown board codename '{}'."
                .format(codename)
            )

        hwid = cros_hwid()
        def hwid_match(item):
            codename, board = item
            try:
                return bool(re.match(board.hwid_match, hwid))
            except:
                return False

        matches = tuple(filter(hwid_match, boards.items()))
        if matches:
            codename, board = matches[0]
            logger.info(
                "Detected board '{}' ('{}') by HWID."
                .format(board.name, board.codename)
            )
            return board

        else:
            logger.warning(
                "Couldn't detect board by HWID."
            )

        compatibles = dt_compatibles()
        def compat_preference(item):
            if item is None:
                return len(compatibles)

            codename, board = item
            try:
                return compatibles.index(board.dt_compatible)
            except ValueError:
                return float("inf")

        match = min((None, *boards.items()), key=compat_preference)
        if match is not None:
            codename, board = match
            logger.info(
                "Detected board '{}' ('{}') by device-tree compatibles."
                .format(board.name, board.codename)
            )
            return board

        else:
            logger.warning(
                "Couldn't detect board by dt-compatibles."
            )

        raise ValueError(
            "Could not detect which board this is running on."
        )

    @config_options.add
    @Argument("--images-dir", nargs=1)
    def images_dir(self, dir_=None):
        """Directory to store built images"""
        if dir_ is None:
            dir_ = self.config.get("images-dir")

        if dir_ is None:
            raise ValueError(
                "Images directory is not specified"
            )

        return Path(dir_)

    @config_options.add
    @Argument("--vboot-keyblock", nargs=1)
    def vboot_keyblock(self, keyblock=None):
        """Keyblock file to include in images"""
        if keyblock is None:
            keyblock = self.config.get("vboot-keyblock")

        return keyblock

    @config_options.add
    @Argument("--vboot-public-key", nargs=1)
    def vboot_public_key(self, signpubkey=None):
        """Public key file to verify images with"""
        if signpubkey is None:
            signpubkey = self.config.get("vboot-public-key")

        return signpubkey

    @config_options.add
    @Argument("--vboot-private-key", nargs=1)
    def vboot_private_key(self, signprivate=None):
        """Private key file to sign images with"""
        if signprivate is None:
            signprivate = self.config.get("vboot-private-key")

        return signprivate

    @config_options.add
    @Argument("--kernel-cmdline", nargs="+", metavar="CMD")
    def kernel_cmdline(self, *cmds):
        """Command line options for the kernel"""
        if len(cmds) == 0:
            cmdline = self.config.get("kernel-cmdline")
            if cmdline is not None:
                cmds = shlex.split(cmdline)

        return list(cmds)

    @config_options.add
    @Argument("--ignore-initramfs", ignore=True)
    def ignore_initramfs(self, ignore=None):
        """Do not include initramfs in images"""
        if ignore is None:
            ignore = self.config.getboolean("ignore-initramfs", False)

        return ignore

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
