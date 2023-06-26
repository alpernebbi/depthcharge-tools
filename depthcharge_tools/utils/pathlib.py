#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools pathlib utilities
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import shutil
import subprocess

from pathlib import Path

from depthcharge_tools.utils.subprocess import (
    gzip,
    lz4,
    lzma,
    lzop,
    bzip2,
    xz,
    zstd,
)

def copy(src, dest):
    dest = shutil.copy2(src, dest)
    return Path(dest)


def decompress(src, dest=None, partial=False):
    if dest is not None:
        dest = Path(dest)

    for runner in (gzip, zstd, xz, lz4, lzma, bzip2, lzop):
        try:
            return runner.decompress(src, dest)

        except FileNotFoundError:
            if dest:
                dest.unlink()

        except subprocess.CalledProcessError as err:
            if dest is None and err.output and partial:
                return err.output

            elif dest and dest.stat().st_size > 0 and partial:
                return dest

            elif dest:
                dest.unlink()


def iterdir(path):
    try:
        if path.is_dir():
            return path.iterdir()
        else:
            return []
    except:
        return []


def read_lines(path):
    try:
        if path.is_file():
            return path.read_text().splitlines()
        else:
            return []
    except:
        return []
