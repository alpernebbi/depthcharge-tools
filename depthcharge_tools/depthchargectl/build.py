#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import (
    __version__,
    config,
    boards,
)
from depthcharge_tools.utils import (
    board_name,
    Disk,
    Partition,
    Command,
    Kernel,
)

logger = logging.getLogger(__name__)


class DepthchargectlBuild(Command):
    def __init__(self, name="depthchargectl build", parent=None):
        super().__init__(name, parent)

    def __call__(
        self,
        kernel_version=None,
        all=False,
        force=False,
        reproducible=False,
    ):
        if all:
            kernels = Kernel.all()
        elif kernel_version is not None:
            kernels = [
                k for k in Kernel.all()
                if k.release == kernel_version
            ]
        else:
            kernels = [max(Kernel.all())]

        board = config.machine
        if board is None:
            board = board_name()

        board = boards[board]
        print(board.name)

        for k in kernels:
            print(k.release)

    def _init_parser(self):
        return super()._init_parser(
            description="Buld a depthcharge image for the running system.",
            usage="%(prog)s [options] [kernel-version]",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            "kernel_version",
            metavar="kernel-version",
            nargs="?",
            help="Installed kernel version to build an image for.",
        )

    def _init_options(self, options):
        options.add_argument(
            "-a", "--all",
            action='store_true',
            help="Build images for all available kernel versions.",
        )
        options.add_argument(
            "-f", "--force",
            action='store_true',
            help="Rebuild images even if existing ones are valid.",
        )
        options.add_argument(
            "--reproducible",
            action='store_true',
            help="Try to build reproducible images.",
        )
