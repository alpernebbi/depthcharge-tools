#! /usr/bin/env python3

import argparse
import logging

from pathlib import Path

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
    CommandExit,
)
from depthcharge_tools.utils.subprocess import (
    mkimage,
    vbutil_kernel,
)

from depthcharge_tools.depthchargectl import depthchargectl

logger = logging.getLogger(__name__)


class SizeTooBigError(CommandExit):
    def __init__(self, image, image_size, max_size):
        message = (
            "Image '{}' ({} bytes) must be smaller than {} bytes."
            .format(image, image_size, max_size)
        )

        self.image = image
        self.image_size = image_size
        self.max_size = max_size
        super().__init__(output=False, returncode=3, message=message)


class NotADepthchargeImageError(CommandExit):
    def __init__(self, image):
        message = (
            "Image '{}' is not a depthcharge image."
            .format(image)
        )

        self.image = image
        super().__init__(output=False, returncode=4, message=message)


class VbootSignatureError(CommandExit):
    def __init__(self, image):
        message = (
            "Depthcharge image '{}' is not signed by the configured keys."
            .format(image)
        )

        self.image = image
        super().__init__(output=False, returncode=5, message=message)


class ImageFormatError(CommandExit):
    def __init__(self, image, board_format):
        message = (
            "Image '{}' must be in '{}' format."
            .format(image, board_format)
        )

        self.image = image
        self.board_format = board_format
        super().__init__(output=False, returncode=6, message=message)


@depthchargectl.subcommand("check")
class depthchargectl_check(
    depthchargectl,
    prog="depthchargectl check",
    usage = "%(prog)s [options] IMAGE",
    add_help=False,
):
    """Check if a depthcharge image can be booted."""

    config_section = "depthchargectl/check"

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument
    def image(self, image):
        """Depthcharge image to check validity of."""
        image = Path(image)

        if not image.is_file():
            raise ValueError("Image argument must be a file")

        return image

    def __call__(self):
        image = self.image

        logger.info(
            "Verifying image for board '{}' ('{}')."
            .format(self.board.name, self.board.codename)
        )

        logger.info("Checking if image fits into size limit.")
        image_size = image.stat().st_size
        if image_size > self.board.image_max_size:
            raise SizeTooBigError(
                image,
                image_size,
                self.board.image_max_size,
            )

        logger.info("Checking depthcharge image validity.")
        if vbutil_kernel(
            "--verify", image,
            check=False,
        ).returncode != 0:
            raise NotADepthchargeImageError(image)

        logger.info("Checking depthcharge image signatures.")
        if self.vboot_public_key is not None:
            if vbutil_kernel(
                "--verify", image,
                "--signpubkey", self.vboot_public_key,
                check=False,
            ).returncode != 0:
                raise VbootSignatureError(image)

        itb = self.tmpdir / "{}.itb".format(image.name)
        vbutil_kernel(
            "--get-vmlinuz", image,
            "--vmlinuz-out", itb,
            check=False,
        )

        if self.board.image_format == "fit":
            logger.info("Checking FIT image format.")
            proc = mkimage("-l", itb)
            if proc.returncode != 0:
                raise ImageFormatError(image, self.board.image_format)

            head = proc.stdout.splitlines()[0]
            if not head.startswith("FIT description:"):
                raise ImageFormatError(image, self.board.image_format)

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
