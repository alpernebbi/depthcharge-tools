#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Path,
    TemporaryDirectory,
    Command,
    Argument,
    Group,
    mkimage,
    vbutil_kernel,
)

from depthcharge_tools.depthchargectl import depthchargectl

logger = logging.getLogger(__name__)


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
        return Path(image)

    def __call__(self):
        image = self.image

        try:
            logger.info(
                "Verifying image for board '{}' ('{}')."
                .format(self.board_name, self.board_codename)
            )
        except KeyError:
            raise ValueError(
                "Cannot verify images for unsupported board '{}'."
                .format(self.board)
            )

        if not image.is_file():
            raise OSError(
                2,
                "Image is not a file."
            )

        logger.info("Checking if image fits into size limit.")
        if image.stat().st_size > self.board_image_max_size:
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
            "--signpubkey", self.vboot_public_key,
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

            if self.board_image_format == "fit":
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

    global_options = depthchargectl.global_options
