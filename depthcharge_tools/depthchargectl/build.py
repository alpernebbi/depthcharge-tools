#! /usr/bin/env python3

import argparse
import logging
import os
import textwrap

from depthcharge_tools import (
    __version__,
    CONFIG,
)
from depthcharge_tools.mkdepthcharge import mkdepthcharge
from depthcharge_tools.utils import (
    board_name,
    root_requires_initramfs,
    vboot_keys,
    Config,
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
                raise ValueError(
                    "Could not find an installed kernel for version '{}'."
                    .format(kernel_version)
                )

        else:
            kernels = [max(Kernel.all())]

        config = Config(CONFIG)
        board = config.machine
        if board is None:
            board = board_name()

        try:
            board = config[board]
        except KeyError:
            raise ValueError(
                "Cannot build images for unsupported board '{}'."
                .format(board)
            )

        for k in kernels:
            logger.info(
                "Building for kernel version '{}'.".format(k.release)
            )

            # vmlinuz is always mandatory
            if k.kernel is None:
                raise ValueError(
                    "No vmlinuz file found for version '{}'."
                    .format(k.release)
                )

            # Initramfs is optional.
            if k.initrd is None:
                logger.info(
                    "No initramfs file found for version '{}'."
                    .format(k.release)
                )

            # Device trees are optional based on board configuration.
            if board.dtb_name is not None:
                if board.image_format == "fit":
                    if k.fdtdir is None:
                        raise ValueError(
                            "No dtb directory found for version '{}', "
                            "but this machine needs a dtb."
                            .format(k.release)
                        )

                    dtbs = sorted(k.fdtdir.glob(
                        "**/{}".format(board.dtb_name)
                    ))

                    if not dtbs:
                        raise ValueError(
                            "No dtb file '{}' found in '{}'."
                            .format(board.dtb_name, k.fdtdir)
                        )

                elif board.image_format == "zimage":
                    raise ValueError(
                        "Image format '{}' doesn't support dtb files "
                        "('{}') required by your board."
                        .format(board.image_format, board.dtb_name)
                    )

            # On at least Debian, the root the system should boot from
            # is included in the initramfs. Custom kernels might still
            # be able to boot without an initramfs, but we need to
            # inject a root= parameter for that.
            cmdline = config.kernel_cmdline or []
            for c in cmdline:
                lhs, _, rhs = c.partition("=")
                if lhs.lower() == "root":
                    root = rhs
                    logger.info(
                        "Using root as set in user configured cmdline."
                    )
                    break
            else:
                logger.info("Trying to prepend root into cmdline.")
                root = findmnt.fstab("/").stdout.rstrip("\n")

                if root:
                    logger.info("Using root as set in /etc/fstab.")
                else:
                    logger.warn(
                        "Couldn't figure out a root cmdline parameter from "
                        "/etc/fstab. Will use '{}' from kernel."
                        .format(root)
                    )
                    root = findmnt.kernel("/").stdout.rstrip("\n")

                if not root:
                    raise ValueError(
                        "Couldn't figure out a root cmdline parameter."
                    )

                # Prepend it so that user-given cmdline overrides it.
                logger.info(
                    "Prepending 'root={}' to kernel cmdline."
                    .format(root)
                )
                cmdline.append("root={}".format(root))

            if config.ignore_initramfs:
                logger.warn(
                    "Ignoring initramfs '{}' as configured, "
                    "appending 'noinitrd' to the kernel cmdline."
                    .format(k.initrd)
                )
                k.initrd = None
                cmdline.append("noinitrd")

            # Linux kernel without an initramfs only supports certain
            # types of root parameters, check for them.
            if k.initrd is None and root_requires_initramfs(root):
                raise ValueError(
                    "An initramfs is required for root '{}'."
                    .format(root)
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

            # Allowed compression levels. We will call mkdepthcharge by
            # hand multiple times for these.
            compress = (
                config.kernel_compression
                or board.kernel_compression
                or ["none"]
            )
            for c in compress:
                if c != "none" and c not in board.kernel_compression:
                    raise ValueError(
                        "Configured to use compression '{}', but this "
                        "board does not support it."
                        .format(c)
                    )

            # zimage doesn't support compression
            if board.image_format == "zimage":
                if compress != ["none"]:
                    raise ValueError(
                        "Image format '{}' doesn't support kernel "
                        "compression formats '{}'."
                        .format(board.image_format, compress)
                    )

            # Try to keep the output reproducible. Initramfs date is
            # bound to be later than vmlinuz date, so prefer that if
            # possible.
            if reproducible and not "SOURCE_DATE_EPOCH" in os.environ:
                if k.initrd is not None:
                    date = int(k.initrd.stat().st_mtime)
                else:
                    date = int(k.kernel.stat().st_mtime)

                if date:
                    os.environ["SOURCE_DATE_EPOCH"] = str(date)
                else:
                    logger.error(
                        "Couldn't determine a date from initramfs "
                        "nor vmlinuz."
                    )

            # Keep images in their own directory, which might not be
            # created at install-time
            images = Path("/boot/depthcharge-tools/images")
            os.makedirs(images, exist_ok=True)

            # Build to temporary files so we do not overwrite existing
            # images with an unbootable image.
            output = images / "{}.img".format(k.release)
            outtmp = images / "{}.img.tmp".format(k.release)
            inputs = images / "{}.img.inputs".format(k.release)
            intmps = images / "{}.img.tmp.inputs".format(k.release)

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

            # Keep information about input files and configuration.
            report = textwrap.dedent("""\
                # Software versions:
                Depthchargectl-Version: {version}
                Mkdepthcharge-Version: {version}

                # Machine info:
                Machine: {board.name}
                DTB-Name: {board.dtb_name}
                Max-Size: {board.image_max_size}
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
                output.exists()
                and inputs.exists()
                and inputs.read_text() == report
            ):
                logger.info(
                    "Inputs are the same with those of existing image, "
                    "no need to rebuild the image."
                )
                if force:
                    logger.info("Rebuilding anyway.")
                else:
                    return output

            intmps.write_text(report)

            for c in compress:
                logger.info("Trying with compression '{}'.".format(c))
                mkdepthcharge(
                    cmdline=cmdline,
                    compress=(c if c != "none" else None),
                    dtbs=dtbs,
                    image_format=board.image_format,
                    initramfs=k.initrd,
                    keyblock=keyblock,
                    name=k.description,
                    output=outtmp,
                    signprivate=signprivate,
                    vmlinuz=k.kernel,
                )

                try:
                    self._parent.check(outtmp)
                    break
                except OSError as err:
                    if err.errno != 3:
                        raise RuntimeError(
                            "Failed while creating depthcharge image."
                        )
                    logger.warn(
                        "Image with compression '{}' is too big "
                        "for this board."
                        .format(c)
                    )
                    if c != compress[-1]:
                        continue
                    logger.error(
                        "The initramfs might be too big for this machine. "
                        "Usually this can be resolved by including less "
                        "modules in the initramfs and/or compressing it "
                        "with a better algorithm. Please check your distro's "
                        "documentation for how to do this."
                    )
                    raise RuntimeError(
                        "Couldn't build a small enough image for this machine."
                    )
            else:
                raise RuntimeError(
                    "Failed to create a valid depthcharge image."
                )

            # If we force-rebuilt the image, and we should've been
            # reproducible, check if it changed.
            if (
                force
                and reproducible
                and output.exists()
                and inputs.read_text() == intmps.read_text()
                and output.read_bytes() != outtmp.read_bytes()
            ):
                logger.warning(
                    "Force-rebuilding image changed it in reproducible "
                    "mode. This is most likely a bug."
                )

            logger.info("Copying newly built image and info to output.")
            intmps.copy_to(inputs)
            outtmp.copy_to(output)
            outtmp.unlink()
            intmps.unlink()

            logger.info(
                "Built image for kernel version '{}'."
                .format(k.release)
            )
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
