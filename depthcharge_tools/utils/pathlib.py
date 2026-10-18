#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools pathlib utilities
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import shutil
import struct
import subprocess

from mmap import mmap, ACCESS_READ
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
    pemagic = None
    coff = None
    if head.startswith(b"MZ"):
        ftype = "mz"
        if len(head) > 0x40:
            pemagic = struct.unpack('<I', head[0x3c:0x40])[0]

    if head.startswith(b"PE\x00\x00"):
        pemagic = 0

    if pemagic and len(head) > pemagic + 4:
        if head[pemagic:pemagic+4] == b"PE\x00\x00":
            ftype = "pe"
        coff = pemagic + 4
        if len(head) < coff + 20:
            return ftype

    if coff is not None:
        suffix = None
        arch = struct.unpack('<H', head[coff:coff+2])[0]
        if arch == 0x8664:
            suffix = "amd64"
        elif arch == 0xaa64:
            suffix = "arm64"
        elif arch in (0x01c0, 0x01c2, 0x01c4):
            suffix = "arm"
        elif arch == 0x014c:
            suffix = "x86"

        optsize = struct.unpack('<H', head[coff+16:coff+18])[0]
        opthdr = coff + 20
        if optsize > 70 and len(head) > (opthdr + 70):
            subsys = struct.unpack('<H', head[opthdr+68:opthdr+70])[0]
            if subsys == 0x0a:
                ftype = "efi"
            if subsys == 0x0b:
                ftype = "efi-driver"
            if subsys == 0x0c:
                ftype = "efi-driver"

        nsections = struct.unpack('<H', head[coff+2:coff+4])[0]
        sections = opthdr + optsize
        if (sections + nsections * 40) > len(head):
            with path.open("rb") as fd:
                head = fd.read(sections + nsections * 40)

        if ftype == "efi":
            snames = []
            for i in range(0, nsections):
                sect = sections + i * 40
                snames.append(head[sect:sect+8])
            if b".linux\x00\x00" in snames:
                ftype = "uki"
            elif (
                b".cmdline" in snames
                or b".dtb\x00\x00\x00\x00" in snames
                or b".dtbauto" in snames
                or b".ucode\x00\x00" in snames
                or b".initrd\x00" in snames
            ):
                ftype = "uki-addon"

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


def pe_sections(path):
    path = Path(path).resolve()
    ftype = guess_filetype(path)
    if not (
        ftype.startswith("pe-")
        or ftype.startswith("efi-")
        or ftype.startswith("uki-")
    ):
        return

    with path.open("rb") as f, mmap(f.fileno(), 0, access=ACCESS_READ) as data:
        pemagic = 0
        if data[:2] == b"MZ":
            ftype = "mz"
            pemagic = struct.unpack('<I', data[0x3c:0x40])[0]

        coff = pemagic + 4
        optsize = struct.unpack('<H', data[coff+16:coff+18])[0]
        opthdr = coff + 20
        nsections = struct.unpack('<H', data[coff+2:coff+4])[0]
        sections = opthdr + optsize
        for i in range(0, nsections):
            sect = sections + i * 40
            name = data[sect:sect+8].decode().rstrip("\0")
            size = struct.unpack('<L', data[sect+16:sect+20])[0]
            pos = struct.unpack('<L', data[sect+20:sect+24])[0]
            yield (name, data[pos:pos+size])


def unukify(path):
    ftype = None
    parts = {
        "linux": None,
        "initrd": [],
        "dtb": None,
        "dtbauto": [],
        "cmdline": [],
        "osrel": {},
        "uname": "",
        "ucode": [],
    }

    for name, data in pe_sections(path):
        if name == ".linux":
            ftype = "uki"
            if parts["linux"] is None:
                parts["linux"] = data
            else:
                raise ValueError(
                    "UKI image cannot have multiple .linux sections"
                )

        elif name == ".initrd":
            ftype = ftype or "uki-addon"
            parts["initrd"].append(data)

        elif name == ".dtb":
            ftype = ftype or "uki-addon"
            parts["dtb"] = data

        elif name == ".dtbauto":
            ftype = ftype or "uki-addon"
            parts["dtbauto"].append(data)

        elif name == ".cmdline":
            ftype = ftype or "uki-addon"
            parts["cmdline"].append(data.rstrip(b"\x00").decode())

        elif name == ".osrel":
            for line in data.rstrip(b"\x00").decode().splitlines():
                lhs, eq, rhs = line.partition("=")
                if eq == "=":
                    parts["osrel"][lhs] = rhs

        elif name == ".uname":
            parts["uname"] = data.rstrip(b"\x00").decode()

        elif name == ".ucode":
            ftype = ftype or "uki-addon"
            parts["ucode"].append(data)

        elif name == ".profile":
            # Only parse default profile
            break

    if ftype is None:
        return None

    return parts
