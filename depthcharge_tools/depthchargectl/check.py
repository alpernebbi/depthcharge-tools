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
    vboot_keys,
    Path,
    Command,
    TemporaryDirectory,
    mkimage,
    vbutil_kernel,
)

logger = logging.getLogger(__name__)


class DepthchargectlCheck(Command):
    def __init__(self, name="depthchargectl check", parent=None):
        super().__init__(name, parent)

    def __call__(self, image):
        image = Path(image)

        board = config.machine
        if board is None:
            board = board_name()

        board = boards[board]

        _, keyblock, signprivate, signpubkey = vboot_keys()
        if config.vboot_keyblock is not None:
            keyblock = config.vboot_keyblock
        if config.vboot_private_key is not None:
            signprivate = config.vboot_private_key
        if config.vboot_public_key is not None:
            signpubkey = config.vboot_public_key

        if not image.is_file():
            return 2

        if image.stat().st_size > board.max_size:
            return 3

        if vbutil_kernel(
            "--verify", image,
            check=False,
        ).returncode != 0:
            return 4

        if vbutil_kernel(
            "--verify", image,
            "--signpubkey", signpubkey,
            check=False,
        ).returncode != 0:
            return 5

        with TemporaryDirectory("-depthchargectl") as tmpdir:
            itb = tmpdir / "{}.itb".format(image.name)
            vbutil_kernel(
                "--get-vmlinuz", image,
                "--vmlinuz-out", itb,
                check=False,
            )

            if board.image_format == "fit":
                proc = mkimage("-l", itb)
                if proc.returncode != 0:
                    return 6

                head = proc.stdout.splitlines()[0]
                if not head.startswith("FIT description:"):
                    return 6

    def _init_parser(self):
        return super()._init_parser(
            description="Check if a depthcharge image can be booted.",
            usage="%(prog)s [options] image",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        arguments.add_argument(
            "image",
            help="Depthcharge image to check validity of.",
        )
