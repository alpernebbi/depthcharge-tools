#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl check subcommand
# Copyright (C) 2020-2023 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

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
    fdtget,
    vbutil_kernel,
)

from depthcharge_tools.depthchargectl import depthchargectl


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


class MissingDTBError(CommandExit):
    def __init__(self, image, compat):
        message = (
            "Image '{}' must have a device-tree binary compatible with pattern '{}'."
            .format(image, compat)
        )

        self.image = image
        self.compat = compat
        super().__init__(output=False, returncode=7, message=message)


@depthchargectl.subcommand("check")
class depthchargectl_check(
    depthchargectl,
    prog="depthchargectl check",
    usage = "%(prog)s [options] IMAGE",
    add_help=False,
):
    """Check if a depthcharge image can be booted."""

    _logger = depthchargectl._logger.getChild("check")
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

    @depthchargectl.board.copy()
    def board(self, codename=""):
        """Assume we're running on the specified board"""
        board = super().board

        if board is None:
            raise ValueError(
                "Cannot check depthcharge images when no board is specified.",
            )

        return board

    @depthchargectl.zimage_initramfs_hack.copy()
    def zimage_initramfs_hack(self, hack=None):
        hack = super().zimage_initramfs_hack

        if hack not in (None, "set-init-size", "pad-vmlinuz"):
            raise ValueError(
                "Unknown zimage initramfs support hack '{}'."
                .format(hack)
            )

        return hack


    def __call__(self):
        image = self.image

        self.logger.warning(
            "Verifying depthcharge image for board '{}' ('{}')."
            .format(self.board.name, self.board.codename)
        )

        self.logger.info("Checking if image fits into size limit.")
        image_size = image.stat().st_size
        if image_size > self.board.image_max_size:
            raise SizeTooBigError(
                image,
                image_size,
                self.board.image_max_size,
            )

        self.logger.info("Checking depthcharge image validity.")
        if vbutil_kernel(
            "--verify", image,
            check=False,
        ).returncode != 0:
            raise NotADepthchargeImageError(image)

        self.logger.info("Checking depthcharge image signatures.")
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
            self.logger.info("Checking FIT image format.")
            nodes = fdtget.subnodes(itb)
            if "images" not in nodes and "configurations" not in nodes:
                raise ImageFormatError(image, self.board.image_format)

            def is_compatible(dt_file, conf_path):
                return any(
                    self.board.dt_compatible.fullmatch(compat)
                    for compat in fdtget.get(
                        dt_file, conf_path, "compatible", default="",
                    ).split()
                )

            self.logger.info("Checking included DTB binaries.")
            for conf in fdtget.subnodes(itb, "/configurations"):
                conf_path = "/configurations/{}".format(conf)
                if is_compatible(itb, conf_path):
                    break

                dtb = fdtget.get(itb, conf_path, "fdt")
                dtb_path = "/images/{}".format(dtb)
                dtb_data = fdtget.get(itb, dtb_path, "data", type=bytes)
                dtb_file = self.tmpdir / "{}.dtb".format(conf)
                dtb_file.write_bytes(dtb_data)

                if is_compatible(dtb_file, "/"):
                    break
            else:
                raise MissingDTBError(
                    image, self.board.dt_compatible.pattern,
                )

        self.logger.warning(
            "This command is incomplete, the image might be unbootable "
            "despite passing currently implemented checks."
        )

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options
