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
        return self._info.name

    @property
    def dtb_name(self):
        return self._info.get("dtb-name")

    @property
    def kernel_compression(self):
        compress = self._info.get("kernel-compression")
        if compress is not None:
            return compress.split(" ")

    @property
    def max_size(self):
        return self._info.getint("max-size")

    @property
    def image_format(self):
        return self._info.get("image-format")


class Config:
    def __init__(self, *paths):
        parser = configparser.ConfigParser()
        parser.add_section("CONFIG")
        for path in paths:
            parser.read_string(
                "\n".join(("[CONFIG]", pathlib.Path(path).read_text())),
                source=path,
            )

        self._parser = parser
        self._config = parser["CONFIG"]

    def __getitem__(self, board):
        section = self._parser[board]
        return Board(section)

    @property
    def machine(self):
        return self._config.get("machine")

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
