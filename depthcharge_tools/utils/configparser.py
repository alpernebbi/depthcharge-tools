#! /usr/bin/env python3

import configparser
import pathlib
import re


class BoardInfo:
    def __init__(self, *paths):
        parser = configparser.ConfigParser()
        parser.SECTCRE = re.compile("^Machine: (?P<header>.*)$")
        parser.read(paths)

        self._parser = parser

    def __getitem__(self, board):
        section = self._parser[board]
        return Board(section)


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
        return self._info.get("kernel-compression")

    @property
    def max_size(self):
        return self._info.get("max-size")

    @property
    def image_format(self):
        return self._info.get("image-format")


class Config:
    def __init__(self, *paths):
        parser = configparser.ConfigParser()
        for path in paths:
            parser.read_string(
                "\n".join(("[CONFIG]", pathlib.Path(path).read_text())),
                source=path,
            )

        self._parser = parser
        self._config = parser["CONFIG"]

    @property
    def machine(self):
        return self._config.get("machine")

    @property
    def kernel_cmdline(self):
        return self._config.get("kernel-cmdline")

    @property
    def kernel_compression(self):
        return self._config.get("kernel-compression")

    @property
    def ignore_initramfs(self):
        return self._config.get("ignore-initramfs")

    @property
    def vboot_keyblock(self):
        return self._config.get("vboot-keyblock")

    @property
    def vboot_public_key(self):
        return self._config.get("vboot-public-key")

    @property
    def vboot_private_key(self):
        return self._config.get("vboot-private-key")
