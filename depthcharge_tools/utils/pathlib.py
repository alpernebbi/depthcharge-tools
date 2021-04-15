#! /usr/bin/env python3

import shutil

from pathlib import Path

from depthcharge_tools.utils.subprocess import (
    gzip as gzip_runner,
    lz4 as lz4_runner,
    lzma as lzma_runner,
)


def copy(src, dest):
    dest = shutil.copy2(src, dest)
    return Path(dest)


def is_gzip(path):
    proc = gzip_runner.test(path)
    return proc.returncode == 0


def gunzip(src, dest=None):
    if dest is None:
        if src.name.endswith(".gz"):
            dest = src.parent / src.name[:-3]
        else:
            dest = src.parent / (src.name + ".gunzip")
    gzip_runner.decompress(src, dest)
    return Path(dest)


def lz4(src, dest=None):
    if dest is None:
        dest = src.parent / (src.name + ".lz4")
    lz4_runner.compress(src, dest)
    return Path(dest)


def lzma(src, dest=None):
    if dest is None:
        dest = src.parent / (src.name + ".lzma")
    lzma_runner.compress(src, dest)
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
