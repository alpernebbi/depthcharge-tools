#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools __init__.py
# Copyright (C) 2020-2021 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import glob
import logging
import pathlib
import pkg_resources
import re
import subprocess

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_version():
    version = None
    pkg_path = pkg_resources.resource_filename(__name__, '')
    pkg_path = pathlib.Path(pkg_path).resolve()

    try:
        self = pkg_resources.require(__name__)[0]
        version = self.version

    except pkg_resources.DistributionNotFound:
        setup_py = pkg_path.parent / "setup.py"
        if setup_py.exists():
            version = re.findall(
                'version=(\'.+\'|".+"),',
                setup_py.read_text(),
            )[0].strip('"\'')

    if (pkg_path.parent / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", pkg_path, "describe"],
            stdout=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
        if proc.returncode == 0:
            tag, *local = proc.stdout.split("-")

            if local:
                version = "{}+{}".format(tag, ".".join(local))
            else:
                version = tag

    if version is not None:
        return pkg_resources.parse_version(version)

__version__ = get_version()

config_ini = pkg_resources.resource_string(__name__, "config.ini")
config_ini = config_ini.decode("utf-8")

boards_ini = pkg_resources.resource_string(__name__, "boards.ini")
boards_ini = boards_ini.decode("utf-8")

config_files = [
    *glob.glob("/etc/depthcharge-tools/config"),
    *glob.glob("/etc/depthcharge-tools/config.d/*"),
]


