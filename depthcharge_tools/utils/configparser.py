#! /usr/bin/env python3

import configparser
import pathlib
import re

from depthcharge_tools import __version__


def read_machinedb():
    parser = configparser.ConfigParser()
    parser.SECTCRE = re.compile("^Machine: (?P<header>.*)$")

    datadir = pathlib.Path("conf")
    parser.read([datadir / "db", datadir / "userdb"])
    return parser


def read_config():
    parser = configparser.ConfigParser()

    confdir = pathlib.Path("conf")
    config = confdir / "config"
    parser.read_string("\n".join(("[DEFAULT]", config.read_text())))
    return parser
