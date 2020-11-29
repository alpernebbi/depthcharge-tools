#! /usr/bin/env python3

import collections
import platform

from depthcharge_tools import __version__
from depthcharge_tools.utils.pathlib import Path


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


class SysDevTree(collections.defaultdict):
    def __init__(self, sys=None, dev=None):
        super().__init__(set)

        sys = Path(sys or "/sys")
        dev = Path(dev or "/dev")

        for sysdir in (sys / "class" / "block").iterdir():
            for device in (sysdir / "dm" / "name").read_lines():
                self.add(dev / "mapper" / device, dev / sysdir.name)

            for device in (sysdir / "slaves").iterdir():
                self.add(dev / sysdir.name, dev / device.name)

            for device in (sysdir / "holders").iterdir():
                self.add(dev / device.name, dev / sysdir.name)

            for device in sysdir.iterdir():
                if device.name.startswith(sysdir.name):
                    self.add(dev / device.name, dev / sysdir.name)

        self.sys = sys
        self.dev = dev

    def add(self, child, parent):
        if child.exists() and parent.exists():
            if child != parent:
                self[child].add(parent)

    def leaves(self, *children):
        ls = set()

        if not children:
            ls.update(*self.values())
            ls.difference_update(self.keys())
            return ls

        children = [Path(c).resolve() for c in children]
        while children:
            c = children.pop(0)
            if c in self:
                for p in self[c]:
                    children.append(p)
            else:
                ls.add(c)

        return ls
