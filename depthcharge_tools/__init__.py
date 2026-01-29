#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools __init__.py
# Copyright (C) 2020-2021 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import glob
import logging
import pathlib
import re
import subprocess
from importlib import metadata, resources

from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_version():
    version = None
    pkg_path = resources.files(__name__)

    try:
        version = metadata.version(__name__)

    except metadata.PackageNotFoundError:
        if isinstance(pkg_path, pathlib.Path):
            setup_py = pkg_path.parent / "setup.py"
            if setup_py.exists():
                version = re.findall(
                    'version=(\'.+\'|".+"),',
                    setup_py.read_text(),
                )[0].strip('"\'')

    if (
        isinstance(pkg_path, pathlib.Path)
        and (pkg_path.parent / ".git").exists()
    ):
        proc = subprocess.run(
            ["git", "-C", pkg_path, "describe"],
            stdout=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
        if proc.returncode == 0:
            tag, *local = proc.stdout.split("-")

            if local:
                git_version = "{}+{}".format(tag, ".".join(local))
            else:
                git_version = tag
            try:
                return Version(git_version)
            except InvalidVersion:
                pass

    if version is not None:
        return Version(version)

__version__ = get_version()

config_ini = resources.files(__name__).joinpath("config.ini").read_text()

boards_ini = resources.files(__name__).joinpath("boards.ini").read_text()

config_files = [
    *glob.glob("/etc/depthcharge-tools/config"),
    *glob.glob("/etc/depthcharge-tools/config.d/*"),
]


