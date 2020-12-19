#! /usr/bin/env python3

import argparse
import logging
import os
import textwrap

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
    sha256sum,
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
            if not kernels:
                raise ValueError("kernel_version")

        else:
            kernels = [max(Kernel.all())]

        board = config.machine
        if board is None:
            board = board_name()

        board = boards[board]

        for k in kernels:
            # vmlinuz is always mandatory
            if k.kernel is None:
                raise ValueError("vmlinuz")

            if board.dtb_name is not None:
                if board.image_format == "fit":
                    if k.fdtdir is None:
                        raise ValueError("kernel.fdtdir")

                    dtbs = sorted(k.fdtdir.glob(
                        "**/{}".format(board.dtb_name)
                    ))

                    if not dtbs:
                        raise ValueError("dtbs")

                elif board.image_format == "zimage":
                    raise ValueError("dtb-zimage")

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

            output = Path(LOCALSTATEDIR / "{}.img".format(k.release))
            outtmp = Path(LOCALSTATEDIR / "{}.img.tmp".format(k.release))
            inputs = Path(LOCALSTATEDIR / "{}.img.inputs".format(k.release))
            intmps = Path(LOCALSTATEDIR / "{}.img.tmp.inputs".format(k.release))

            infiles = [
                f for f in (
                    k.kernel,
                    k.initrd,
                    *dtbs,
                    keyblock,
                    signpubkey,
                    signprivate,
                )
                if f is not None
            ]

            report = textwrap.dedent("""\
                # Software versions:
                Depthchargectl-Version: {version}
                Mkdepthcharge-Version: {version}

                # Machine info:
                Machine: {board.name}
                DTB-Name: {board.dtb_name}
                Max-Size: {board.max_size}
                Kernel-Compression: {board_compress}
                Image-Format: {board.image_format}

                # Image configuration:
                Kernel-Version: {kernel.release}
                Kernel-Cmdline: {cmdline}
                Kernel-Compression: {compress}
                Kernel-Name: {kernel.description}
                Source-Date-Epoch: {epoch}

                # Image inputs:
                Vmlinuz: {kernel.kernel}
                Initramfs: {kernel.initrd}
                {dtbs}

                # Signing keys:
                Vboot-Keyblock: {keyblock}
                Vboot-Public-Key: {signpubkey}
                Vboot-Private-Key: {signprivate}

                # SHA256 checksums:
                {sha256sums}
            """).rstrip("\n").format(
                version=__version__,
                board=board,
                kernel=k,
                board_compress=" ".join(board.kernel_compression),
                compress=" ".join(compress),
                cmdline=" ".join(cmdline),
                epoch=os.environ.get("SOURCE_DATE_EPOCH", "unset"),
                dtbs=("\n".join("DTB: {}".format(d) for d in dtbs)),
                keyblock=keyblock,
                signpubkey=signpubkey,
                signprivate=signprivate,
                sha256sums=sha256sum(*infiles).stdout
            )

            if (
                not force
                and output.exists()
                and inputs.exists()
                and inputs.read_text() == report
            ):
                return output

            intmps.write_text(report)

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

            if (
                force
                and reproducible
                and output.exists()
                and inputs.read_text() == intmps.read_text()
                and output.read_bytes() != outtmp.read_bytes()
            ):
                logger.warning("was not reproducible")

            intmps.copy_to(inputs)
            outtmp.copy_to(output)
            outtmp.unlink()
            intmps.unlink()

            return output

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
