#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools os utilities
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import collections
import re
import shlex

from pathlib import Path

from depthcharge_tools.utils.collections import (
    DirectedGraph,
)
from depthcharge_tools.utils.pathlib import (
    iterdir,
    read_lines,
)
from depthcharge_tools.utils.platform import (
    proc_cmdline,
)
from depthcharge_tools.utils.subprocess import (
    cgpt,
)


class Disks(DirectedGraph):
    def __init__(
        self,
        sys="/sys",
        dev="/dev",
        fstab="/etc/fstab",
        mtab="/etc/mtab",
        procmounts="/proc/self/mounts",
        mountinfo="/proc/self/mountinfo",
        crypttab="/etc/crypttab",
    ):
        super().__init__()

        self._sys = sys = Path(sys)
        self._dev = dev = Path(dev)
        self._fstab = fstab = Path(fstab)
        self._procmounts = procmounts = Path(procmounts)
        self._mtab = mtab = Path(mtab)
        self._mountinfo = mountinfo = Path(mountinfo)
        self._crypttab = crypttab = Path(crypttab)

        for sysdir in iterdir(sys / "class" / "block"):
            for device in read_lines(sysdir / "dm" / "name"):
                self.add_edge(dev / sysdir.name, dev / "mapper" / device)

            for device in iterdir(sysdir / "slaves"):
                self.add_edge(dev / device.name, dev / sysdir.name)

            for device in iterdir(sysdir / "holders"):
                self.add_edge(dev / sysdir.name, dev / device.name)

            for device in iterdir(sysdir):
                if device.name.startswith(sysdir.name):
                    self.add_edge(dev / sysdir.name, dev / device.name)

        for line in read_lines(crypttab):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                cryptdev, device = fields[0], fields[1]
                if device != 'none':
                    cryptdev = dev / "mapper" / cryptdev
                    self.add_edge(device, cryptdev)

        fstab_mounts = {}
        for line in read_lines(fstab):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                device, mount = fields[0], fields[1]
                if mount != 'none':
                    fstab_mounts[mount] = device

        procmounts_mounts = {}
        for line in read_lines(procmounts):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                device, mount = fields[0], fields[1]
                device = self.evaluate(device)
                if device is not None:
                    procmounts_mounts[mount] = device

        mtab_mounts = {}
        for line in read_lines(mtab):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                device, mount = fields[0], fields[1]
                device = self.evaluate(device)
                if device is not None:
                    mtab_mounts[mount] = device

        mountinfo_mounts = {}
        for line in read_lines(mountinfo):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                device, fsroot, mount = fields[2], fields[3], fields[4]
                if fsroot != "/":
                    mountinfo_mounts[mount] = None
                    continue
                device = self.evaluate(device)
                if device is not None:
                    mountinfo_mounts[mount] = device

        mounts = collections.ChainMap(
            fstab_mounts,
            mountinfo_mounts,
            procmounts_mounts,
            mtab_mounts,
        )

        self._fstab_mounts = fstab_mounts
        self._procmounts_mounts = procmounts_mounts
        self._mtab_mounts = mtab_mounts
        self._mountinfo_mounts = mountinfo_mounts
        self._mounts = mounts

    def __getitem__(self, key):
        return self.evaluate(key)

    def evaluate(self, device):
        dev = self._dev
        sys = self._sys

        if device is None:
            return None

        elif isinstance(device, Path):
            device = str(device)

        elif isinstance(device, (Disk, Partition)):
            device = str(device.path)

        if device.startswith("ID="):
            id_ = device[len("ID="):]
            if not id_:
                return None

            device = dev / "disk" / "by-id" / id_

        elif device.startswith("LABEL="):
            label = device[len("LABEL="):]
            if not label:
                return None

            device = dev / "disk" / "by-label" / label

        elif device.startswith("PARTLABEL="):
            partlabel = device[len("PARTLABEL="):]
            if not partlabel:
                return None

            device = dev / "disk" / "by-partlabel" / partlabel

        elif device.startswith("UUID="):
            uuid = device[len("UUID="):]
            if not uuid:
                return None

            device = dev / "disk" / "by-uuid" / uuid
            if not device.exists():
                device = dev / "disk" / "by-uuid" / uuid.lower()

        elif device.startswith("PARTUUID="):
            partuuid, _, partnroff = (
                device[len("PARTUUID="):].partition("/PARTNROFF=")
            )
            if not partuuid:
                return None

            device = dev / "disk" / "by-partuuid" / partuuid
            if not device.exists():
                device = dev / "disk" / "by-partuuid" / partuuid.lower()

            if partnroff:
                device = device.resolve()
                match = re.match("(.*[^0-9])([0-9]+)$", device.name)
                if not match:
                    return None
                prefix, partno = match.groups()
                partno = str(int(partno) + int(partnroff))
                device = device.with_name("{}{}".format(prefix, partno))

        elif re.match("[0-9]+:[0-9]+", device):
            device = dev / "block" / device

        # Encrypted devices may currently be set up with names different
        # than in the crypttab file, so check that as well.
        elif device.startswith(str(dev / "mapper")):
            if not Path(device).resolve().exists():
                for line in read_lines(self._crypttab):
                    if not line or line.startswith("#"):
                        continue

                    fields = shlex.split(line)
                    parentdev, cryptdev = fields[1], fields[0]
                    if cryptdev != device.split("/")[-1]:
                        continue

                    parentdev = self.evaluate(parentdev)
                    siblings = self.children(parentdev)
                    if len(siblings) == 1:
                        device = str(siblings.pop())

                    # This is actually wrong, but we can't really decide
                    # which to use. The parent's good enough for us since
                    # we usually only care about going up the tree.
                    else:
                        device = str(parentdev)

        device = Path(device).resolve()
        if not device.exists() or dev not in device.parents:
            return None

        try:
            return Partition(device, dev=dev, sys=sys)
        except:
            pass

        try:
            return Disk(device, dev=dev, sys=sys)
        except:
            pass

    def by_mountpoint(self, mountpoint, fstab_only=False):
        if not Path(mountpoint).exists():
            return None

        if fstab_only:
            # We want the form in the fstab, e.g. PARTUUID=*
            device = self._fstab_mounts.get(mountpoint)
            return device
        else:
            device = self._mounts.get(str(mountpoint))
            return self.evaluate(device)

    def mountpoints(self, device, include_fstab=False):
        device = self.evaluate(device)
        if device is None:
            return set()

        # Exclude fstab whose entries are not necessarily mounted
        if not include_fstab:
            mounts = collections.ChainMap(
                self._mountinfo_mounts,
                self._procmounts_mounts,
                self._mtab_mounts,
            )
        else:
            mounts = self._mounts

        mountpoints = set()
        for mnt, dev in mounts.items():
            dev = self.evaluate(dev)
            if dev == device:
                mnt = Path(mnt).resolve()
                if mnt.exists() or include_fstab:
                    mountpoints.add(mnt)

        return mountpoints

    def by_id(self, id_):
        return self.evaluate("ID={}".format(id_))

    def by_label(self, label):
        return self.evaluate("LABEL={}".format(label))

    def by_partlabel(self, partlabel):
        return self.evaluate("PARTLABEL={}".format(partlabel))

    def by_uuid(self, uuid):
        return self.evaluate("UUID={}".format(uuid))

    def by_partuuid(self, partuuid):
        return self.evaluate("PARTUUID={}".format(partuuid))

    def _get_dev_disk_info(self, device, prop):
        device = self.evaluate(device)
        for path in self._dev.glob("disk/by-{}/*".format(prop)):
            dev = self.evaluate(path)
            if dev == device:
                return path.name

    def get_id(self, device):
        return self._get_dev_disk_info(device, "id")

    def get_label(self, device):
        return self._get_dev_disk_info(device, "label")

    def get_partlabel(self, device):
        return self._get_dev_disk_info(device, "partlabel")

    def get_uuid(self, device):
        return self._get_dev_disk_info(device, "uuid")

    def get_partuuid(self, device):
        return self._get_dev_disk_info(device, "partuuid")

    def by_kern_guid(self):
        for arg in proc_cmdline():
            lhs, _, rhs = arg.partition("=")
            if lhs == "kern_guid":
                return self.by_partuuid(rhs)

    def add_edge(self, node, child):
        node = self.evaluate(node)
        child = self.evaluate(child)
        if node is not None and child is not None and node != child:
            return super().add_edge(node, child)

    def children(self, *nodes):
        return super().children(*map(self.evaluate, nodes))

    def parents(self, *nodes):
        return super().parents(*map(self.evaluate, nodes))

    def leaves(self, *nodes):
        return super().leaves(*map(self.evaluate, nodes))

    def roots(self, *nodes):
        return super().roots(*map(self.evaluate, nodes))


class Disk:
    def __init__(self, path, dev="/dev", sys="/sys"):
        self._sys = sys = Path(sys)
        self._dev = dev = Path(dev)

        if isinstance(path, Disk):
            path = path.path
        else:
            path = Path(path).resolve()

        if not (path.is_file() or path.is_block_device()):
            fmt = "Disk '{}' is not a file or block device."
            msg = fmt.format(str(path))
            raise ValueError(msg)

        self.path = path

    def partition(self, partno):
        return Partition(self, partno, dev=self._dev, sys=self._sys)

    def partitions(self):
        return [
            Partition(self, n, dev=self._dev, sys=self._sys)
            for n in cgpt.find_partitions(self.path)
        ]

    def cros_partitions(self):
        return [
            CrosPartition(self, n, dev=self._dev, sys=self._sys)
            for n in cgpt.find_partitions(self.path, type="kernel")
        ]

    @property
    def size(self):
        if self.path.is_file():
            return self.path.stat().st_size

        if self.path.is_block_device():
            sysdir = self._sys / "class" / "block" / self.path.name

            size_f = sysdir / "size"
            if size_f.exists():
                blocks = int(size_f.read_text())
                return blocks * 512

    def __hash__(self):
        return hash((self.path,))

    def __eq__(self, other):
        if isinstance(other, Disk):
            return self.path == other.path
        return False

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        cls = self.__class__.__name__
        return "{}('{}')".format(cls, self.path)


class Partition:
    def __init__(self, path, partno=None, dev="/dev", sys="/sys"):
        self._dev = dev = Path(dev)
        self._sys = sys = Path(sys)

        if isinstance(path, Disk):
            disk = path
            path = None
        elif isinstance(path, Partition):
            disk = path.disk
            partno = path.partno
            path = path.path
        else:
            disk = None
            path = Path(path).resolve()

        if (
            disk is None
            and partno is None
            and path.parent == dev
            and path.is_block_device()
        ):
            match = (
                re.fullmatch("(.*[0-9])p([0-9]+)", path.name)
                or re.fullmatch("(.*[^0-9])([0-9]+)", path.name)
            )
            if match:
                diskname, partno = match.groups()
                partno = int(partno)
                disk = Disk(path.with_name(diskname), dev=dev, sys=sys)

        if disk is None:
            disk = Disk(path, dev=dev, sys=sys)
            path = None

        if partno is None:
            fmt = "Partition number not given for disk '{}'."
            msg = fmt.format(str(disk))
            raise ValueError(msg)

        elif not (isinstance(partno, int) and partno > 0):
            fmt = "Partition number '{}' must be a positive integer."
            msg = fmt.format(partno)
            raise ValueError(msg)

        elif (
            path is None
            and disk.path.parent == dev
            and disk.path.is_block_device()
        ):
            fmt = "{}p{}" if disk.path.name[-1].isnumeric() else "{}{}"
            name = fmt.format(disk.path.name, partno)
            path = disk.path.with_name(name)

        if path is not None:
            if not (path.is_file() or path.is_block_device()):
                path = None

        self.disk = disk
        self.path = path
        self.partno = partno

    @property
    def size(self):
        if self.path is None:
            return cgpt.get_size(self.disk.path, self.partno)

        if self.path.is_file():
            return self.path.stat().st_size

        if self.path.is_block_device():
            sysdir = self._sys / "class" / "block" / self.path.name

            size_f = sysdir / "size"
            if size_f.exists():
                blocks = int(size_f.read_text())
                return blocks * 512

    def write_bytes(self, data):
        data = bytes(data)

        if len(data) >= self.size:
            raise ValueError(
                "Data to be written ('{}' bytes) is bigger than "
                "partition '{}' ('{}' bytes)."
                .format(len(data), self, self.size)
            )

        if self.path is None:
            start = cgpt.get_start(self.disk.path, self.partno)

            with self.disk.path.open("r+b") as disk:
                seek = disk.seek(start)
                if seek != start:
                    raise IOError(
                        "Couldn't seek disk to start of partition '{}'."
                        .format(self)
                    )

                written = disk.write(data)
                if written != len(data):
                    raise IOError(
                        "Couldn't write data to partition '{}' "
                        "(wrote '{}' out of '{}' bytes)."
                        .format(self, written, len(data))
                    )

        else:
            self.path.write_bytes(data)

    def __hash__(self):
        return hash((self.path, self.disk, self.partno))

    def __eq__(self, other):
        if isinstance(other, Partition):
            return (
                self.path == other.path
                and self.disk == other.disk
                and self.partno == other.partno
            )
        return False

    def __str__(self):
        if self.path is not None:
            return str(self.path)
        else:
            return "{}#{}".format(self.disk.path, self.partno)

    def __repr__(self):
        cls = self.__class__.__name__
        if self.path is not None:
            return "{}('{}')".format(cls, self.path)
        else:
            return "{}('{}', {})".format(cls, self.disk.path, self.partno)


class CrosPartition(Partition):
    @property
    def attribute(self):
        return cgpt.get_raw_attribute(self.disk.path, self.partno)

    @attribute.setter
    def attribute(self, attr):
        return cgpt.set_raw_attribute(self.disk.path, self.partno, attr)

    @property
    def flags(self):
        flags = cgpt.get_flags(self.disk.path, self.partno)
        return {
            "attribute": flags["A"],
            "successful": flags["S"],
            "priority": flags["P"],
            "tries": flags["T"],
        }

    @flags.setter
    def flags(self, value):
        if isinstance(value, dict):
            A = value.get("attribute", None)
            S = value.get("successful", None)
            P = value.get("priority", None)
            T = value.get("tries", None)

        else:
            A = getattr(value, "attribute", None)
            S = getattr(value, "successful", None)
            P = getattr(value, "priority", None)
            T = getattr(value, "tries", None)

        cgpt.set_flags(self.disk.path, self.partno, A=A, S=S, P=P, T=T)

    @property
    def successful(self):
        return self.flags["successful"]

    @successful.setter
    def successful(self, value):
        self.flags = {"successful": value}

    @property
    def tries(self):
        return self.flags["tries"]

    @tries.setter
    def tries(self, value):
        self.flags = {"tries": value}

    @property
    def priority(self):
        return self.flags["priority"]

    @priority.setter
    def priority(self, value):
        self.flags = {"priority": value}

    def prioritize(self):
        return cgpt.prioritize(self.disk.path, self.partno)

    def _comparable_parts(self):
        flags = self.flags
        size = self.size

        return (
            flags["successful"],
            flags["priority"],
            flags["tries"],
            self.size,
        )

    def __lt__(self, other):
        if not isinstance(other, CrosPartition):
            return NotImplemented

        return self._comparable_parts() < other._comparable_parts()

    def __gt__(self, other):
        if not isinstance(other, CrosPartition):
            return NotImplemented

        return self._comparable_parts() > other._comparable_parts()
