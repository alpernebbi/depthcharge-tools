#! /usr/bin/env python3

import glob
import logging
import pathlib
import pkg_resources
import re
import subprocess

from depthcharge_tools.utils import (
    Config,
    BoardInfo,
)

logger = logging.getLogger(__name__)
log_handler = logging.StreamHandler()
logger.addHandler(log_handler)


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


config_files = [
    pkg_resources.resource_filename(__name__, "config"),
    *glob.glob("/usr/share/depthcharge-tools/config"),
    *glob.glob("/usr/share/depthcharge-tools/config.d/*"),
]
config = Config(*config_files)

db_files = [
    pkg_resources.resource_filename(__name__, "db"),
    *glob.glob("/usr/share/depthcharge-tools/db"),
    pkg_resources.resource_filename(__name__, "userdb"),
    *glob.glob("/etc/depthcharge-tools/userdb"),
    *glob.glob("/etc/depthcharge-tools/userdb.d/*"),
]
boards = BoardInfo(*db_files)
