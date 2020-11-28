#! /usr/bin/env python3

import argparse
import logging
import sys
import types

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
    Command,
    LoggingLevelAction,
)
from depthcharge_tools.depthchargectl import (
    build,
    check,
    partitions,
    rm,
    set_good,
    target,
    write,
)

logger = logging.getLogger(__name__)


class Depthchargectl(Command):
    Build = build.DepthchargectlBuild
    Check = check.DepthchargectlCheck
    Partitions = partitions.DepthchargectlPartitions
    Rm = rm.DepthchargectlRm
    SetGood = set_good.DepthchargectlSetGood
    Target = target.DepthchargectlTarget
    Write = write.DepthchargectlWrite

    def __init__(self, name="depthchargectl", parent=None):
        super().__init__(name, parent)

    def __call__(self):
        self.partitions()

    def _init_parser(self):
        return super()._init_parser(
            description="Manage Chrome OS kernel partitions.",
            usage="%(prog)s [options] command ...",
            add_help=False,
        )

    def _init_globals(self, options):
        options.add_argument(
            "-h", "--help",
            action='help',
            help="Show this help message.",
        )
        options.add_argument(
            "--version",
            action='version',
            version="depthcharge-tools %(prog)s {}".format(__version__),
            help="Print program version.",
        )
        options.add_argument(
            "-v", "--verbose",
            dest=argparse.SUPPRESS,
            action=LoggingLevelAction,
            level="-10",
            help="Print more detailed output.",
        )

    def _init_commands(self):
        self.build = Depthchargectl.Build('build', self)
        self.check = Depthchargectl.Check('check', self)
        self.partitions = Depthchargectl.Partitions('partitions', self)
        self.rm = Depthchargectl.Rm('rm', self)
        self.set_good = Depthchargectl.SetGood('set-good', self)
        self.target = Depthchargectl.Target('target', self)
        self.write = Depthchargectl.Write('write', self)


depthchargectl = Depthchargectl()


if __name__ == "__main__":
    depthchargectl._main()
