#! /usr/bin/env python3

import configparser
import collections
import re

from pathlib import Path


def parse_recovery_conf(path):
    recovery_conf = Path(path)

    def parse_block(block):
        values = {}

        for line in block.splitlines():
            if line.startswith("#"):
                continue

            key, eq, value = line.partition("=")
            if eq != "=":
                raise ValueError("no equals sign in line: '{}'".format(line))

            if key not in values:
                values[key] = value
            elif isinstance(values[key], list):
                values[key].append(value)
            else:
                values[key] = [values[key], value]

        if "hwidmatch" in values:
            values["hwidmatch"] = re.compile(values["hwidmatch"])
        if "filesize" in values:
            values["filesize"] = int(values["filesize"] or 0)
        if "zipfilesize" in values:
            values["zipfilesize"] = int(values["zipfilesize"] or 0)

        return values

    header, *boards = [
        parse_block(block)
        for block in re.split("\n\n+", recovery_conf.read_text())
    ]

    version = header.get(
        "recovery_tool_linux_version",
        header.get("recovery_tool_version"),
    )

    if version != "0.9.2":
        raise TypeError(
            "Unsupported recovery.conf version: {}"
            .format(header.get("recovery_tool_update", version))
        )

    return boards

