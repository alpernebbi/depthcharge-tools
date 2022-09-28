#! /usr/bin/env python3

import shutil

from pathlib import Path


def copy(src, dest):
    dest = shutil.copy2(src, dest)
    return Path(dest)


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
