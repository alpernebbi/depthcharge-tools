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

    DATADIR = pathlib.Path("/usr/share")
    SYSCONFDIR = pathlib.Path("/etc")

    config_files = [
        pkg_resources.resource_filename(__name__, "config"),
        *SYSCONFDIR.glob("depthcharge-tools/config"),
        *SYSCONFDIR.glob("depthcharge-tools/config.d/*"),
    ]

    db_files = [
        pkg_resources.resource_filename(__name__, "db"),
        *DATADIR.glob("depthcharge-tools/db"),
        pkg_resources.resource_filename(__name__, "userdb"),
        *SYSCONFDIR.glob("depthcharge-tools/userdb"),
        *SYSCONFDIR.glob("depthcharge-tools/userdb.d/*"),
    ]


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

        config_files = [
            *path.glob("depthcharge_tools/config"),
        ]

        db_files = [
            *path.glob("depthcharge_tools/db"),
            *path.glob("depthcharge_tools/userdb"),
        ]

        break


logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
logger.addHandler(log_handler)

if VERSION is not None:
    VERSION = pkg_resources.parse_version(VERSION)
__version__ = VERSION

config = Config(*config_files)
boards = BoardInfo(*db_files)
