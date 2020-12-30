#! /usr/bin/env python3

import configparser
import logging
import pathlib
import pkg_resources
import subprocess
import sys

from depthcharge_tools.utils import (
    Config,
    BoardInfo,
)

try:
    self = pkg_resources.require(__name__)[0]
    PACKAGENAME = self.project_name
    VERSION = self.version
    GITHASH = None

    dirs = pkg_resources.resource_filename(__name__, "dirs")
    dirconfig = configparser.ConfigParser()
    dirconfig.optionxform = str.upper
    dirconfig.read(dirs)
    dirconfig = dirconfig["DEFAULT"]

    DATADIR = pathlib.Path(dirconfig.get("DATADIR"))
    SYSCONFDIR = pathlib.Path(dirconfig.get("SYSCONFDIR"))
    LOCALSTATEDIR = pathlib.Path(dirconfig.get("LOCALSTATEDIR"))

except pkg_resources.DistributionNotFound:
    PACKAGENAME = "depthcharge-tools"
    VERSION = None
    GITHASH = None

    for path in sys.path:
        path = pathlib.Path(path).resolve()

        init = path / "depthcharge_tools" / "__init__.py"
        if not init.exists():
            continue

        git = path / ".git"
        if git.exists():
            proc = subprocess.run(
                ["git", "-C", path, "describe"],
                stdout=subprocess.PIPE,
                encoding="utf-8",
                check=False,
            )
            if proc.returncode == 0:
                VERSION, _ , GITHASH = proc.stdout.partition("-g")

        DATADIR = path / "conf"
        SYSCONFDIR = path / "conf"
        LOCALSTATEDIR = path / "var"

        break


logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
logger.addHandler(log_handler)

VERSION = pkg_resources.parse_version(VERSION)
__version__ = VERSION


config = Config(SYSCONFDIR / "config")
boards = BoardInfo(DATADIR / "db", DATADIR / "userdb")
