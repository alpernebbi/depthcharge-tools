#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools string utilities
# Copyright (C) 2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import ast
import re

def bytesize_suffixes():
    def long_forms(x):
        formats = ("{}", "{}byte", "{} byte", "{}bytes", "{} bytes")
        cases = (str.upper, str.lower, str.title)
        for f in formats:
            for c in cases:
                yield c(f.format(x))

    for size, suffixes in {
        1:       ("B", "byte", "bytes", ""),
        1e3:     ("kB", "KB", *long_forms("kilo")),
        1e6:     ("MB", *long_forms("mega")),
        1e9:     ("GB", *long_forms("giga")),
        1e12:    ("TB", *long_forms("tera")),
        1e15:    ("PB", *long_forms("peta")),
        1e18:    ("EB", *long_forms("exa")),
        1e21:    ("ZB", *long_forms("zetta")),
        1e24:    ("YB", *long_forms("yotta")),
        2 ** 10: ("kiB", "KiB", "K", *long_forms("kibi")),
        2 ** 20: ("MiB", "M", *long_forms("mebi")),
        2 ** 30: ("GiB", "G", *long_forms("gibi")),
        2 ** 40: ("TiB", "T", *long_forms("tebi")),
        2 ** 50: ("PiB", "P", *long_forms("pebi")),
        2 ** 60: ("EiB", "E", *long_forms("exbi")),
        2 ** 70: ("ZiB", "Z", *long_forms("zebi")),
        2 ** 80: ("YiB", "Y", *long_forms("yobi")),
    }.items():
        for suffix in suffixes:
            yield (suffix.strip(), int(size))

bytesize_suffixes = dict(bytesize_suffixes())


def parse_bytesize(val):
    if val is None:
        return None

    try:
        return int(val)
    except:
        pass

    try:
        return int(ast.literal_eval(val))
    except:
        pass

    try:
        s = str(val)
        suffix = re.search("[a-zA-Z\s]*\Z", s)[0].strip()
        number = s.rpartition(suffix)[0].strip()
        multiplier = bytesize_suffixes[suffix]
        return int(ast.literal_eval(number)) * multiplier

    except Exception as err:
        raise ValueError(
            "Cannot convert '{}' to a byte-size."
            .format(val)
        )
