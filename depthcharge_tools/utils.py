#! /usr/bin/env python3

import argparse
import collections
import logging
import os
import pathlib
import shutil
import subprocess
import tempfile

from depthcharge_tools import __version__

logger = logging.getLogger(__name__)


def find_disks(*args):
    block = Path("/sys/class/block")
    devs = [block / dev for dev in os.listdir(block)]
    parents = collections.defaultdict(set)

    for dev in devs:
        dm_name_path = dev / "dm" / "name"
        if dm_name_path.is_file():
            dm_name = dm_name_path.read_text()
            parents[dm_name].add(dev.name)

        slaves_path = dev / "slaves"
        if slaves_path.is_dir():
            for slave in os.listdir(slaves_path):
                parents[slave].add(dev.name)

        parent = dev.resolve().parent
        if parent.parent.name == "block":
            parents[dev.name].add(parent.name)
        elif parent.name == "block":
            parents[dev.name].add(dev.name)

    if len(args) == 0:
        args = parents.keys()

    disks = {
        Path(arg).resolve().name
        for arg in args
        if arg is not None
    }

    phys_disks = set()
    while disks:
        phys_disks.update(*(parents.get(d, set()) for d in disks))
        if disks == phys_disks:
            break
        disks = phys_disks
        phys_disks = set()

    phys_disk_devs = []
    for disk in phys_disks:
        dev = Path("/dev") / disk
        if dev.is_block_device():
            phys_disk_devs.append(dev)

    return phys_disk_devs


class Path(pathlib.PosixPath):
    def copy_to(self, dest):
        dest = shutil.copy2(self, dest)
        return Path(dest)

    def is_gzip(self):
        proc = subprocess.run(["gzip", "-t", self])
        return proc.returncode == 0

    def gunzip(self, dest=None):
        if dest is None:
            if self.name.endswith(".gz"):
                dest = self.parent / self.name[:-3]
            else:
                dest = self.parent / (self.name + ".gunzip")

        with self.open() as s:
            with dest.open('w') as d:
                proc = subprocess.run(["gzip", "-d"], stdin=s, stdout=d)
        proc.check_returncode()
        return Path(dest)

    def lz4(self, dest=None):
        if dest is None:
            dest = self.parent / (self.name + ".lz4")

        with self.open() as s:
            with dest.open('w') as d:
                proc = subprocess.run(["lz4", "-z", "-9"], stdin=s, stdout=d)
        proc.check_returncode()
        return Path(dest)

    def lzma(self, dest=None):
        if dest is None:
            dest = self.parent / (self.name + ".lzma")

        with self.open() as s:
            with dest.open('w') as d:
                proc = subprocess.run(["lzma", "-z"], stdin=s, stdout=d)
        proc.check_returncode()
        return Path(dest)

    def is_vmlinuz(self):
        return any((
            "vmlinuz" in self.name,
            "vmlinux" in self.name,
            "linux" in self.name,
            "Image" in self.name,
            "kernel" in self.name,
        ))

    def is_initramfs(self):
        return any((
            "initrd" in self.name,
            "initramfs" in self.name,
            "cpio" in self.name,
        ))

    def is_dtb(self):
        return any((
            "dtb" in self.name,
        ))


class Architecture(str):
    arm_32 = ["arm"]
    arm_64 = ["arm64", "aarch64"]
    arm = arm_32 + arm_64
    x86_32 = ["i386", "x86"]
    x86_64 = ["x86_64", "amd64"]
    x86 = x86_32 + x86_64
    all = arm + x86
    groups = (arm_32, arm_64, x86_32, x86_64)

    def __eq__(self, other):
        if isinstance(other, Architecture):
            for group in self.groups:
                if self in group and other in group:
                    return True
        return str(self) == str(other)

    def __ne__(self, other):
        if isinstance(other, Architecture):
            for group in self.groups:
                if self in group and other not in group:
                    return True
        return str(self) != str(other)

    @property
    def mkimage(self):
        if self in self.arm_32:
            return "arm"
        if self in self.arm_64:
            return "arm64"
        if self in self.x86_32:
            return "x86"
        if self in self.x86_64:
            return "x86_64"

    @property
    def vboot(self):
        if self in self.arm_32:
            return "arm"
        if self in self.arm_64:
            return "aarch64"
        if self in self.x86_32:
            return "x86"
        if self in self.x86_64:
            return "amd64"


class TemporaryDirectory(tempfile.TemporaryDirectory):
    def __enter__(self):
        return Path(super().__enter__())


class MixedArgumentsAction(argparse.Action):
    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        cls._selectors = {}
        cls._nargs = {}

    def __init__(self, option_strings, dest, select=None, **kwargs):
        super().__init__(option_strings, dest, **kwargs)
        self._selectors[select] = self.dest
        self._nargs[dest] = self.nargs

    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            return
        elif values is getattr(namespace, self.dest):
            return
        elif not isinstance(values, list):
            values = [values]

        for value in values:
            chosen_dest = None
            for select, dest in self._selectors.items():
                if callable(select) and select(value):
                    chosen_dest = dest

            if chosen_dest is not None:
                try:
                    self._set_value(namespace, chosen_dest, value)
                    continue
                except argparse.ArgumentError as err:
                    parser.error(err.message)

            for dest, nargs in self._nargs.items():
                try:
                    self._set_value(namespace, dest, value)
                    break
                except argparse.ArgumentError as err:
                    continue
            else:
                parser.error(err.message)

    def _set_value(self, namespace, dest, value):
        nargs = self._nargs[dest]
        current = getattr(namespace, dest)

        if nargs is None or nargs == "?":
            if current is not None:
                fmt = "Cannot have multiple {} args '{}' and '{}'."
                msg = fmt.format(dest, current, value)
                raise argparse.ArgumentError(self, msg)
            else:
                setattr(namespace, dest, value)

        elif isinstance(nargs, int) and len(current) > nargs:
            fmt = "Cannot have more than {} {} args {}."
            msg = fmt.format(nargs, dest, current + value)
            raise argparse.ArgumentError(self, msg)

        elif current is None:
            setattr(namespace, dest, [value])

        else:
            current.append(value)

