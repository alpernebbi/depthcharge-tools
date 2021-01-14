#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import (
    __version__,
    CONFIG,
)
from depthcharge_tools.utils import (
    board_name,
    vboot_keys,
    Config,
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

        config = Config(CONFIG)
        board = config.board
        if board is None:
            board = board_name()

        try:
            board = config[board]
        except KeyError:
            raise ValueError(
                "Cannot verify images for unsupported board '{}'."
                .format(board)
            )

        # Default to OS-distributed keys, override with custom
        # values if given.
        _, keyblock, signprivate, signpubkey = vboot_keys()
        if config.vboot_keyblock is not None:
            keyblock = config.vboot_keyblock
        if config.vboot_private_key is not None:
            signprivate = config.vboot_private_key
        if config.vboot_public_key is not None:
            signpubkey = config.vboot_public_key

        if not image.is_file():
            raise OSError(
                2,
                "Image is not a file."
            )

        logger.info("Checking if image fits into size limit.")
        if image.stat().st_size > board.image_max_size:
            raise OSError(
                3,
                "Depthcharge image is too big for this machine.",
            )

        logger.info("Checking depthcharge image validity.")
        if vbutil_kernel(
            "--verify", image,
            check=False,
        ).returncode != 0:
            raise OSError(
                4,
                "Image couldn't be interpreted by vbutil_kernel.",
            )

        logger.info("Checking depthcharge image signatures.")
        if vbutil_kernel(
            "--verify", image,
            "--signpubkey", signpubkey,
            check=False,
        ).returncode != 0:
            raise OSError(
                5,
                "Depthcharge image not signed by configured keys.",
            )

        with TemporaryDirectory("-depthchargectl") as tmpdir:
            itb = tmpdir / "{}.itb".format(image.name)
            vbutil_kernel(
                "--get-vmlinuz", image,
                "--vmlinuz-out", itb,
                check=False,
            )

            if board.image_format == "fit":
                logger.info("Checking FIT image format.")
                proc = mkimage("-l", itb)
                if proc.returncode != 0:
                    raise OSError(
                        6,
                        "Packed vmlinuz image not recognized by mkimage.",
                    )

                head = proc.stdout.splitlines()[0]
                if not head.startswith("FIT description:"):
                    raise OSError(
                        6,
                        "Packed vmlinuz image is not a FIT image.",
                    )

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
