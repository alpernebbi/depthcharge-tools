#! /usr/bin/env python3

import shutil

from pathlib import Path

from depthcharge_tools.utils.subprocess import (
    gzip as gzip_runner,
    lz4 as lz4_runner,
    lzma as lzma_runner,
    lzop as lzop_runner,
    bzip2 as bzip2_runner,
    xz as xz_runner,
    zstd as zstd_runner,
)


def copy(src, dest):
    dest = shutil.copy2(src, dest)
    return Path(dest)


def is_gzip(path):
    proc = gzip_runner.test(path)
    return proc.returncode == 0


def is_lz4(path):
    proc = lz4_runner.test(path)
    return proc.returncode == 0


def is_lzma(path):
    proc = lzma_runner.test(path)
    return proc.returncode == 0


def is_lzop(path):
    proc = lzop_runner.test(path)
    return proc.returncode == 0


def is_bzip2(path):
    proc = bzip2_runner.test(path)
    return proc.returncode == 0


def is_xz(path):
    proc = xz_runner.test(path)
    return proc.returncode == 0


def is_zstd(path):
    proc = zstd_runner.test(path)
    return proc.returncode == 0


def gunzip(src, dest=None):
    if dest is None:
        if src.name.endswith(".gz"):
            dest = src.parent / src.name[:-3]
        else:
            dest = src.parent / (src.name + ".gunzip")
    gzip_runner.decompress(src, dest)
    return Path(dest)


def unlz4(src, dest=None):
    if dest is None:
        if src.name.endswith(".lz4"):
            dest = src.parent / src.name[:-4]
        else:
            dest = src.parent / (src.name + ".unlz4")
    lz4_runner.decompress(src, dest)
    return Path(dest)


def unlzma(src, dest=None):
    if dest is None:
        if src.name.endswith(".lzma"):
            dest = src.parent / src.name[:-5]
        else:
            dest = src.parent / (src.name + ".unlzma")
    lzma_runner.decompress(src, dest)
    return Path(dest)


def unlzop(src, dest=None):
    if dest is None:
        if src.name.endswith(".lzo"):
            dest = src.parent / src.name[:-4]
        else:
            dest = src.parent / (src.name + ".unlzop")
    lzop_runner.decompress(src, dest)
    return Path(dest)


def bunzip2(src, dest=None):
    if dest is None:
        if src.name.endswith(".bz2"):
            dest = src.parent / src.name[:-4]
        else:
            dest = src.parent / (src.name + ".bunzip2")
    bzip2_runner.decompress(src, dest)
    return Path(dest)


def unxz(src, dest=None):
    if dest is None:
        if src.name.endswith(".xz"):
            dest = src.parent / src.name[:-3]
        else:
            dest = src.parent / (src.name + ".unxz")
    xz_runner.decompress(src, dest)
    return Path(dest)


def unzstd(src, dest=None):
    if dest is None:
        if src.name.endswith(".zst"):
            dest = src.parent / src.name[:-4]
        else:
            dest = src.parent / (src.name + ".unzstd")
    zstd_runner.decompress(src, dest)
    return Path(dest)


def gzip(src, dest=None):
    if dest is None:
        dest = src.parent / (src.name + ".gz")
    gzip_runner.compress(src, dest)
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


def lzop(src, dest=None):
    if dest is None:
        dest = src.parent / (src.name + ".lzo")
    lzop_runner.compress(src, dest)
    return Path(dest)


def bzip2(src, dest=None):
    if dest is None:
        dest = src.parent / (src.name + ".bz2")
    bzip2_runner.compress(src, dest)
    return Path(dest)


def xz(src, dest=None):
    if dest is None:
        dest = src.parent / (src.name + ".xz")
    xz_runner.compress(src, dest)
    return Path(dest)


def zstd(src, dest=None):
    if dest is None:
        dest = src.parent / (src.name + ".zst")
    zstd_runner.compress(src, dest)
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
