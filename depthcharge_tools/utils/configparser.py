#! /usr/bin/env python3

import configparser
import pathlib
import re
import shlex


class Board:
    def __init__(self, info):
        self._info = info

    @property
    def name(self):
        return self._info.get("name")

    @property
    def codename(self):
        return self._info.get("codename")

    @property
    def dtb_name(self):
        return self._info.get("dtb-name")

    @property
    def dt_compatible(self):
        return self._info.get("dt-compatible")

    @property
    def kernel_compression(self):
        compress = self._info.get("kernel-compression")
        if compress is not None:
            return compress.split(" ")

    @property
    def image_max_size(self):
        return self._info.getint("image-max-size")

    @property
    def image_format(self):
        return self._info.get("image-format")


class Config:
    def __init__(self, parser):
        self._parser = parser
        self._config = parser[parser.default_section]

    def __getitem__(self, codename):
        for name, section in self._parser.items():
            if section.get("codename") == codename:
                return Board(section)
        raise KeyError(codename)

    @property
    def board(self):
        return self._config.get("board")

    @property
    def kernel_cmdline(self):
        cmdline = self._config.get("kernel-cmdline")
        if cmdline is not None:
            return shlex.split(cmdline)

    @property
    def kernel_compression(self):
        compress = self._config.get("kernel-compression")
        if compress is not None:
            return compress.split(" ")

    @property
    def ignore_initramfs(self):
        return self._config.getboolean("ignore-initramfs", False)

    @property
    def vboot_keyblock(self):
        return self._config.get("vboot-keyblock")

    @property
    def vboot_public_key(self):
        return self._config.get("vboot-public-key")

    @property
    def vboot_private_key(self):
        return self._config.get("vboot-private-key")
