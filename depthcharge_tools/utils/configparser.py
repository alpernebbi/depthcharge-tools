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
    def hwid_match(self):
        pattern = self._info.get("hwid-match")
        if pattern:
            return re.compile(pattern)

    @property
    def kernel_lz4(self):
        return self._info.getboolean("kernel-lz4", False)

    @property
    def kernel_lzma(self):
        return self._info.getboolean("kernel-lzma", False)

    @property
    def kernel_compression(self):
        compress = ["none"]
        if self.kernel_lz4:
            compress += ["lz4"]
        if self.kernel_lzma:
            compress += ["lzma"]
        return compress

    @property
    def image_max_size(self):
        return self._info.getint("image-max-size")

    @property
    def image_format(self):
        return self._info.get("image-format")
