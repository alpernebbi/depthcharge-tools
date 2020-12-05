#! /usr/bin/env python3

import tempfile

from depthcharge_tools.utils.pathlib import Path


class TemporaryDirectory(tempfile.TemporaryDirectory):
    def __enter__(self):
        return Path(super().__enter__())
