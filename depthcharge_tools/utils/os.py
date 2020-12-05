#! /usr/bin/env python3

import re

from depthcharge_tools import __version__
from depthcharge_tools.utils.pathlib import Path
from depthcharge_tools.utils.platform import (
    kernel_cmdline,
    SysDevTree
)
from depthcharge_tools.utils.subprocess import (
    cgpt,
    findmnt,
    blockdev,
)


class Disk:
    tree = SysDevTree()

    def __init__(self, path):
        if isinstance(path, Disk):
            path = path.path
        else:
            path = Path(path).resolve()

        if not (path.is_file() or path.is_block_device()):
            fmt = "Disk '{}' is not a file or block device."
            msg = fmt.format(str(path))
            raise ValueError(msg)

        self.path = path

    def disks(*args, bootable=False):
        if bootable:
            boot = Disk.by_mount("/boot")
            if boot is not None:
                args = (*args, boot)

            root = Disk.by_mount("/")
            if root is not None:
                args = (*args, root)

        children = []
        for arg in args:
            if isinstance(arg, Partition):
                children.append(arg.path or arg.disk.path)
            elif isinstance(arg, Disk):
                children.append(arg.path)
            elif arg is not None:
                children.append(arg)

        disks = []
        for path in sorted(Disk.tree.leaves(*children)):
            try:
                dev = Disk(Path("/dev") / path)
                disks.append(dev)
            except ValueError:
                pass

        return disks

    @classmethod
    def by_mount(cls, mnt):
        for fstab in (True, False):
            proc = findmnt.find(mnt, fstab=True)
            if proc.returncode == 0:
                return Path(proc.stdout.strip())

    @classmethod
    def by_partuuid(cls, partuuid):
        proc = cgpt("find", "-1", "-u", partuuid)
        return Path(proc.stdout.strip())

    @classmethod
    def by_kern_guid(cls):
        for arg in kernel_cmdline():
            lhs, _, rhs = arg.partition("=")
            if lhs == "kern_guid":
                return cls.by_partuuid(rhs)

    def partition(self, partno):
        return Partition(self, partno)

    def partitions(self):
        proc = cgpt("find", "-n", "-t", "kernel", self.path)
        return [
            Partition(self, int(n))
            for n in proc.stdout.splitlines()
        ]

    def __repr__(self):
        cls = self.__class__.__name__
        return "{}('{}')".format(cls, self.path)


class Partition:
    def __init__(self, path, partno=None):
        if isinstance(path, Disk):
            disk = path
            path = None
        else:
            disk = None
            path = Path(path).resolve()

        if (
            disk is None
            and partno is None
            and path.parent == Path("/dev")
            and path.is_block_device()
        ):
            match = (
                re.fullmatch("(.*[0-9])p([0-9]+)", path.name)
                or re.fullmatch("(.*[^0-9])([0-9]+)", path.name)
            )
            if match:
                diskname, partno = match.groups()
                partno = int(partno)
                disk = Disk(path.with_name(diskname))

        if disk is None:
            disk = Disk(path)

        if partno is None:
            fmt = "Partition number not given for disk '{}'."
            msg = fmt.format(str(disk))
            raise ValueError(msg)

        elif not (isinstance(partno, int) and partno > 0):
            fmt = "Partition number '{}' must be a positive integer."
            msg = fmt.format(partno)
            raise ValueError(msg)

        elif path is None:
            fmt = "{}p{}" if disk.path.name[-1].isnumeric() else "{}{}"
            name = fmt.format(disk.path.name, partno)
            path = disk.path.with_name(name)

        if not (path.is_file() or path.is_block_device()):
            path = None

        self.disk = disk
        self.path = path
        self.partno = partno

    @property
    def attribute(self):
        proc = cgpt("show", "-A", "-i", str(self.partno), self.disk.path)
        attr = int(proc.stdout, 16)
        return attr

    @attribute.setter
    def attribute(self, attr):
        cgpt("add", "-A", hex(attr), "-i", str(self.partno), self.disk.path)

    @property
    def successful(self):
        return (self.attribute >> 8) & 0x1

    @successful.setter
    def successful(self, s):
        cgpt("add", "-S", str(s), "-i", str(self.partno), self.disk.path)

    @property
    def tries(self):
        return (self.attribute >> 4) & 0xF

    @tries.setter
    def tries(self, t):
        cgpt("add", "-T", str(t), "-i", str(self.partno), self.disk.path)

    @property
    def priority(self):
        return (self.attribute >> 0) & 0xF

    @priority.setter
    def priority(self, p):
        cgpt("add", "-P", str(p), "-i", str(self.partno), self.disk.path)

    def prioritize(self):
        cgpt("prioritize", "-i", str(self.partno), self.disk.path)

    @property
    def size(self):
        if self.path is not None:
            proc = blockdev("--getsize64", self.path)
            return int(proc.stdout)

        proc = cgpt("show", "-s", "-i", str(self.partno), self.disk.path)
        return int(proc.stdout) * 512

    def __repr__(self):
        cls = self.__class__.__name__
        if self.path is not None:
            return "{}('{}')".format(cls, self.path)
        else:
            return "{}('{}', {})".format(cls, self.disk.path, self.partno)
