#! /usr/bin/env python3

import argparse
import logging
import os
import shlex
import textwrap

from depthcharge_tools import __version__
from depthcharge_tools.mkdepthcharge import mkdepthcharge
from depthcharge_tools.utils import (
    root_requires_initramfs,
    Disk,
    Partition,
    Path,
    Kernel,
    Command,
    Argument,
    Group,
    findmnt,
    sha256sum,
)

from depthcharge_tools.depthchargectl import depthchargectl

logger = logging.getLogger(__name__)


@depthchargectl.subcommand("build")
class depthchargectl_build(
    depthchargectl,
    prog="depthchargectl build",
    usage="%(prog)s [options] [KERNEL_VERSION]",
    add_help=False,
):
    """Buld a depthcharge image for the running system."""

    config_section = "depthchargectl/build"

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument
    def kernel_version(self, kernel_version=None):
        """Installed kernel version to build an image for."""

        if kernel_version is not None:
            kernels = [
                k for k in Kernel.all()
                if k.release == kernel_version
            ]
            if not kernels:
                raise ValueError(
                    "Could not find an installed kernel for version '{}'."
                    .format(kernel_version)
                )
            kernel = kernels[0]

        else:
            kernel = max(Kernel.all())

        return kernel

    @property
    def kernel_cmdline(self):
        cmdline = self.config.get("kernel-cmdline")
        if cmdline is not None:
            return shlex.split(cmdline)

    @property
    def ignore_initramfs(self):
        return self.config.getboolean("ignore-initramfs", False)

    @property
    def kernel_release(self):
        return self.kernel_version.release

    @property
    def kernel(self):
        # vmlinuz is always mandatory
        if self.kernel_version.kernel is None:
            raise ValueError(
                "No vmlinuz file found for version '{}'."
                .format(self.kernel_release)
            )

        return self.kernel_version.kernel

    @property
    def initrd(self):
        if self.ignore_initramfs:
            logger.warn(
                "Ignoring initramfs '{}' as configured."
                .format(self.kernel_version.initrd)
            )
            return None

        # Initramfs is optional.
        elif self.kernel_version.initrd is None:
            logger.info(
                "No initramfs file found for version '{}'."
                .format(self.kernel_release)
            )

        return self.kernel_version.initrd

    @property
    def fdtdir(self):
        # Device trees are optional based on board configuration.
        if (
            self.board_dtb_name is not None
            and self.board_image_format == "fit"
            and self.kernel_version.fdtdir is None
        ):
            raise ValueError(
                "No dtb directory found for version '{}', "
                "but this machine needs a dtb."
                .format(self.kernel_release)
            )

        return self.kernel_version.fdtdir

    @property
    def dtbs(self):
        fdtdir = self.fdtdir

        if fdtdir is None:
            raise ValueError(
                "No dtb directory found for version '{}', "
                "but this machine needs a dtb."
                .format(self.kernel_release)
            )

        dtbs = sorted(fdtdir.glob(
            "**/{}".format(self.board_dtb_name)
        ))

        if not dtbs:
            raise ValueError(
                "No dtb file '{}' found in '{}'."
                .format(self.board_dtb_name, fdtdir)
            )

        elif self.board_image_format == "zimage":
            raise ValueError(
                "Image format '{}' doesn't support dtb files "
                "('{}') required by your board."
                .format(self.board_image_format, self.board_dtb_name)
            )

        return dtbs

    @property
    def description(self):
        return self.kernel_version.description

    @property
    def root(self):
        # On at least Debian, the root the system should boot from
        # is included in the initramfs. Custom kernels might still
        # be able to boot without an initramfs, but we need to
        # inject a root= parameter for that.
        cmdline = self.kernel_cmdline or []
        for c in cmdline:
            lhs, _, rhs = c.partition("=")
            if lhs.lower() == "root":
                root = rhs
                logger.info(
                    "Using root as set in user configured cmdline."
                )
                return root

        logger.info("Trying to figure out a root for cmdline.")
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

        return root

    @property
    def cmdline(self):
        cmdline = self.kernel_cmdline or []
        root = self.root

        if 'root={}'.format(self.root) not in cmdline:
            logger.info(
                "Prepending 'root={}' to kernel cmdline."
                .format(root)
            )
            cmdline.append("root={}".format(root))

        if self.ignore_initramfs:
            logger.warn(
                "Ignoring initramfs as configured, "
                "appending 'noinitrd' to the kernel cmdline."
                .format(self.initrd)
            )
            cmdline.append("noinitrd")

        # Linux kernel without an initramfs only supports certain
        # types of root parameters, check for them.
        if self.initrd is None and root_requires_initramfs(root):
            raise ValueError(
                "An initramfs is required for root '{}'."
                .format(root)
            )

        return cmdline

    @property
    def compress(self):
        # Allowed compression levels. We will call mkdepthcharge by
        # hand multiple times for these.

        # zimage doesn't support compression
        if self.board_image_format == "zimage":
            return ["none"]

        compress = ["none"]
        if self.board_boots_lz4_kernel:
            compress += ["lz4"]
        if self.board_boots_lzma_kernel:
            compress += ["lzma"]

        return compress

    @property
    def timestamp(self):
        # Try to keep the output reproducible. Initramfs date is
        # bound to be later than vmlinuz date, so prefer that if
        # possible.
        if "SOURCE_DATE_EPOCH" not in os.environ:
            if self.initrd is not None:
                date = int(self.initrd.stat().st_mtime)
            else:
                date = int(self.kernel.stat().st_mtime)

            if date:
                os.environ["SOURCE_DATE_EPOCH"] = str(date)
            else:
                logger.error(
                    "Couldn't determine a date from initramfs "
                    "nor vmlinuz."
                )

        return os.environ["SOURCE_DATE_EPOCH"]

    @property
    def images_dir(self):
        # Keep images in their own directory, which might not be
        # created at install-time
        images_dir = Path("/boot/depthcharge-tools/images")
        os.makedirs(images_dir, exist_ok=True)

        return images_dir

    @property
    def output(self):
        output = self.images_dir / "{}.img".format(self.kernel_release)

        return output

    def __call__(self):
        try:
            logger.info(
                "Building images for board '{}' ('{}')."
                .format(self.board_name, self.board_codename)
            )
        except KeyError:
            raise ValueError(
                "Cannot build images for unsupported board '{}'."
                .format(self.board)
            )

        logger.info(
            "Building for kernel version '{}'."
            .format(self.kernel_release)
        )

        # Build to a temporary file so we do not overwrite existing
        # images with an unbootable image.
        outtmp = self.images_dir / "{}.img.tmp".format(self.kernel_release)

        for compress in self.compress:
            logger.info("Trying with compression '{}'.".format(compress))
            mkdepthcharge(
                cmdline=self.cmdline,
                compress=compress,
                dtbs=self.dtbs,
                image_format=self.board_image_format,
                initramfs=self.initrd,
                keyblock=self.vboot_keyblock,
                name=self.description,
                output=outtmp,
                signprivate=self.vboot_private_key,
                vmlinuz=self.kernel,
            )

            try:
                depthchargectl.check(image=outtmp)
                break
            except OSError as err:
                if err.errno != 3:
                    raise RuntimeError(
                        "Failed while creating depthcharge image."
                    )
                logger.warn(
                    "Image with compression '{}' is too big "
                    "for this board."
                    .format(compress)
                )
                if compress != self.compress[-1]:
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

        logger.info("Copying newly built image and info to output.")
        outtmp.copy_to(self.output)
        outtmp.unlink()

        logger.info(
            "Built image for kernel version '{}'."
            .format(self.kernel_release)
        )
        return self.output

    global_options = depthchargectl.global_options

