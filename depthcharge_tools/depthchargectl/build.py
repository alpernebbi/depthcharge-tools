#! /usr/bin/env python3

import argparse
import logging
import os

from depthcharge_tools import (
    __version__,
    LOCALSTATEDIR,
    config,
    boards,
)
from depthcharge_tools.mkdepthcharge import mkdepthcharge
from depthcharge_tools.utils import (
    board_name,
    root_requires_initramfs,
    vboot_keys,
    Disk,
    Partition,
    Path,
    Command,
    Kernel,
    findmnt,
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

        for k in kernels:
            if board.image_format == "fit":
                if board.dtb_name is not None:
                    if k.fdtdir is None:
                        raise ValueError("kernel.fdtdir")

                    dtbs = sorted(k.fdtdir.glob(
                        "**/{}".format(board.dtb_name)
                    ))

                    if not dtbs:
                        raise ValueError("dtbs")

            cmdline = config.kernel_cmdline or []
            for c in cmdline:
                lhs, _, rhs = c.partition("=")
                if lhs.lower() == "root":
                    root = rhs
                    break
            else:
                root = findmnt.fstab("/").stdout.rstrip("\n")
                if not root:
                    root = findmnt.kernel("/").stdout.rstrip("\n")
                if not root:
                    raise ValueError("root")

                cmdline.append("root={}".format(root))

            if config.ignore_initramfs:
                k.initrd = None
                cmdline.append("noinitrd")

            if k.initrd is None and root_requires_initramfs(root):
                raise ValueError("root-initramfs")

            _, keyblock, signprivate, signpubkey = vboot_keys()
            if config.vboot_keyblock is not None:
                keyblock = config.vboot_keyblock
            if config.vboot_private_key is not None:
                signprivate = config.vboot_private_key
            if config.vboot_public_key is not None:
                signpubkey = config.vboot_public_key

            compress = (
                config.kernel_compression
                or board.kernel_compression
                or ["none"]
            )
            for c in compress:
                if c != "none" and c not in board.kernel_compression:
                    raise ValueError("compress")

            if reproducible and not "SOURCE_DATE_EPOCH" in os.environ:
                if k.initrd is not None:
                    date = int(k.initrd.stat().st_mtime)
                else:
                    date = int(k.kernel.stat().st_mtime)
                os.environ["SOURCE_DATE_EPOCH"] = str(date)

            # write_inputs()

            output = Path(LOCALSTATEDIR / "{}.img".format(k.release))
            outtmp = Path(LOCALSTATEDIR / "{}.img.tmp".format(k.release))

            for c in compress:
                mkdepthcharge(
                    cmdline=cmdline,
                    compress=c,
                    dtbs=dtbs,
                    image_format=board.image_format,
                    initramfs=k.initrd,
                    keyblock=keyblock,
                    name=k.description,
                    output=outtmp,
                    signprivate=signprivate,
                    vmlinuz=k.kernel,
                )

                # check(outtmp)

                if outtmp.stat().st_size < board.max_size:
                    break
            else:
                raise RuntimeError("output")

            # check_reproducible()

            outtmp.copy_to(output)
            outtmp.unlink()
            print(output)

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
