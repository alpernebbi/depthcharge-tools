#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools pathlib utilities
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import shutil
import struct
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
            out = runner.decompress(src, dest)
            if out in (None, "", b""):
                continue
            if isinstance(out, Path) and out.stat().st_size == 0:
                out.unlink(missing_ok=True)
                continue
            return out

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


def guess_filetype(path):
    try:
        path = Path(path).resolve()
    except:
        return "error"

    if path.is_block_device():
        return "blockdev"
    if path.is_char_device():
        return "chardev"
    if path.is_mount():
        return "mount"
    if path.is_dir():
        return "directory"

    head = None
    try:
        with path.open("rb") as fd:
            head = fd.read(4096)
    except:
        return "error"

    if not head:
        return "empty"

    if len(head) > 0x206 and head[0x202:0x206] == b"HdrS":
        return "linux-x86"

    if len(head) > 0x3c and head[0x38:0x3c] == b"ARM\x64":
        return "linux-arm64"

    if len(head) > 0x38 and head[0x34:0x38] == b"\x45\x45\x45\x45":
        return "linux-arm"

    if head.startswith(b"\x7fELF") and len(head) > 0x14:
        if head[0x12:0x14] == b"\x03\x00":
            return "elf-x86"
        if head[0x12:0x14] == b"\x28\x00":
            return "elf-arm"
        if head[0x12:0x14] == b"\x3e\x00":
            return "elf-amd64"
        if head[0x12:0x14] == b"\xb7\x00":
            return "elf-arm64"
        return "elf"

    ftype = None
    coff = None
    if head.startswith(b"MZ") and len(head) > 0x40:
        ftype = "pe"
        coff = struct.unpack('<I', head[0x3c:0x40])[0]
        if len(head) < coff+6:
            return ftype

    if head.startswith(b"PE\x00\x00"):
        ftype = "coff"
        coff = 0
        if len(head) < coff+6:
            return ftype

    if coff is not None:
        suffix = None
        arch = struct.unpack('<H', head[coff+0x04:coff+0x06])[0]
        if arch == 0x8664:
            suffix = "amd64"
        elif arch == 0xaa64:
            suffix = "arm64"
        elif arch in (0x01c0, 0x01c2, 0x01c4):
            suffix = "arm"
        elif arch == 0x014c:
            suffix = "x86"

        optsize = struct.unpack('<H', head[coff+0x14:coff+0x16])[0]
        if optsize > 0x5e and len(head) > (coff + 0x5e):
            subsys = struct.unpack('<H', head[coff+0x5c:coff+0x5e])[0]
            if subsys == 0x0a:
                ftype = "efi"
            if subsys == 0x0b:
                ftype = "efi-driver"
            if subsys == 0x0c:
                ftype = "efi-driver"

        return f"{ftype}-{suffix}" if suffix else ftype

    for magic, filetype in {
        b"\xd0\x0d\xfe\xed":    "dtb",
        b"070701":              "cpio",
        b"070702":              "cpio",
        b"070707":              "cpio",
        b'\x1f\x8b':            "gzip",
        b'\xfd7zXZ\x00':        "xz",
        b'(\xb5/\xfd':          "zstd",
        b'\x5d\x00\x00\x00':    "lzma",
        b'\02!L\x18':           "lz4",
        b'BZh':                 "bzip2",
        b'\x89\x4c\x5a':        "lzop",
    }.items():
        if head.startswith(magic):
            return filetype

    return "unknown"
