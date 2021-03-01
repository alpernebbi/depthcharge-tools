#! /usr/bin/env python3

import collections
import pathlib
import re
import shlex

from depthcharge_tools.utils.pathlib import Path
from depthcharge_tools.utils.platform import (
    kernel_cmdline,
)
from depthcharge_tools.utils.subprocess import (
    cgpt,
)


class Disks:
    def __init__(
        self,
        sys="/sys",
        dev="/dev",
        fstab="/etc/fstab",
        mtab="/etc/mtab",
        mountinfo="/proc/self/mountinfo",
    ):
        self._edges = {}

        self._sys = sys = pathlib.Path(sys)
        self._dev = dev = pathlib.Path(dev)
        self._fstab = fstab = pathlib.Path(fstab)
        self._mtab = mtab = pathlib.Path(mtab)
        self._mountinfo = mountinfo = pathlib.Path(mountinfo)

        def iterdir(path):
            return path.iterdir() if path.is_dir() else []

        def read_lines(path):
            return path.read_text().splitlines() if path.is_file() else []

        for sysdir in iterdir(sys / "class" / "block"):
            for device in read_lines(sysdir / "dm" / "name"):
                self.add_edge(dev / sysdir.name, dev / "mapper" / device)

            for device in iterdir(sysdir / "slaves"):
                self.add_edge(dev / device.name, dev / sysdir.name)

            for device in iterdir(sysdir / "holders"):
                self.add_edge(dev / sysdir.name, dev / device.name)

            for device in sysdir.iterdir():
                if device.name.startswith(sysdir.name):
                    self.add_edge(dev / sysdir.name, dev / device.name)

        fstab_mounts = {}
        for line in read_lines(fstab):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                device, mount = fields[0], fields[1]
                fstab_mounts[mount] = device

        mtab_mounts = {}
        for line in read_lines(mtab):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                device, mount = fields[0], fields[1]
                mtab_mounts[mount] = device

        mountinfo_mounts = {}
        for line in read_lines(mountinfo):
            if line and not line.startswith("#"):
                fields = shlex.split(line)
                device, mount = fields[9], fields[4]
                mountinfo_mounts[mount] = device

        mounts = collections.ChainMap(
            fstab_mounts,
            mountinfo_mounts,
            mtab_mounts,
        )

        self._fstab_mounts = fstab_mounts
        self._mtab_mounts = mtab_mounts
        self._mountinfo_mounts = mountinfo_mounts
        self._mounts = mounts

    def __getitem__(self, key):
        return self.evaluate(key)

    def evaluate(self, device):
        dev = self._dev

        if device is None:
            return None

        elif isinstance(device, pathlib.Path):
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

        device = Path(device).resolve()
        if not device.exists() or dev not in device.parents:
            return None

        try:
            return Partition(device)
        except:
            return Disk(device)

    def by_mountpoint(self, mountpoint, fstab_only=False):
        if not Path(mountpoint).exists():
            return None

        if fstab_only:
            # We want the form in the fstab, e.g. PARTUUID=*
            device = self._fstab_mounts.get(mountpoint)
            return device
        else:
            device = self._mounts.get(mountpoint)
            return self.evaluate(device)

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

    def by_kern_guid(self):
        for arg in kernel_cmdline():
            lhs, _, rhs = arg.partition("=")
            if lhs == "kern_guid":
                return self.by_partuuid(rhs)

    def bootable_disks(self):
        root = self.by_mountpoint("/")
        boot = self.by_mountpoint("/boot")
        disks = set(self.evaluate(d) for d in (root, boot))
        return self.roots(*disks)

    def add_edge(self, node, child):
        node = self.evaluate(node)
        child = self.evaluate(child)

        if node is None or child is None or node == child:
            return

        if node not in self._edges:
            self._edges[node] = set()

        self._edges[node].add(child)

    def children(self, *nodes):
        nodes = set(self.evaluate(n) for n in nodes)
        node_children = set()
        for node in nodes:
            node_children.update(self._edges.get(node, set()))

        return node_children

    def parents(self, *nodes):
        nodes = set(self.evaluate(n) for n in nodes)
        node_parents = set()
        for parent, children in self._edges.items():
            if children.intersection(nodes):
                node_parents.add(parent)

        return node_parents

    def leaves(self, *nodes):
        nodes = set(self.evaluate(n) for n in nodes)

        leaves = set()
        if len(nodes) == 0:
            leaves.update(*self._edges.values())
            leaves.difference_update(self._edges.keys())
            return leaves

        leaves = self.leaves()
        node_leaves = set()
        while nodes:
            node_leaves.update(nodes.intersection(leaves))
            nodes.difference_update(node_leaves)
            nodes = self.children(*nodes)

        return node_leaves

    def roots(self, *nodes):
        nodes = set(self.evaluate(n) for n in nodes)

        roots = set()
        if len(nodes) == 0:
            roots.update(self._edges.keys())
            roots.difference_update(*self._edges.values())
            return roots

        roots = self.roots()
        node_roots = set()
        while nodes:
            node_roots.update(nodes.intersection(roots))
            nodes.difference_update(node_roots)
            nodes = self.parents(*nodes)

        return node_roots


class Disk:
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

    def partition(self, partno):
        return Partition(self, partno)

    def partitions(self):
        proc = cgpt("show", "-q", "-n", self.path)
        return [
            Partition(self, int(shlex.split(line)[2]))
            for line in proc.stdout.splitlines()
        ]

    def cros_partitions(self):
        proc = cgpt("find", "-n", "-t", "kernel", self.path)
        return [
            CrosPartition(self, int(n))
            for n in proc.stdout.splitlines()
        ]

    @property
    def size(self):
        if self.path.is_file():
            return self.path.stat().st_size

        if self.path.is_block_device():
             sysdir = Path("/sys/class/block") / self.path.name
             return int((sysdir / "size").read_text()) * 512

    def __hash__(self):
        return hash((self.path,))

    def __eq__(self, other):
        if isinstance(other, Disk):
            return self.path == other.path
        return False

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
    def size(self):
        if self.path is None:
            proc = cgpt("show", "-s", "-i", str(self.partno), self.disk.path)
            blocks = int(proc.stdout)
            return blocks * 512

        if self.path.is_file():
            return self.path.stat().st_size

        if self.path.is_block_device():
             sysdir = Path("/sys/class/block") / self.path.name
             blocks = int((sysdir / "size").read_text())
             return blocks * 512

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

    def __repr__(self):
        cls = self.__class__.__name__
        if self.path is not None:
            return "{}('{}')".format(cls, self.path)
        else:
            return "{}('{}', {})".format(cls, self.disk.path, self.partno)


class CrosPartition(Partition):
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


system_disks = Disks()
