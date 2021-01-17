#! /usr/bin/env python3

import argparse
import logging
import platform
import sys

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    mkimage,
    vbutil_kernel,
    vboot_keys,
    Architecture,
    Path,
    TemporaryDirectory,
    LoggingLevelAction,
    MixedArgumentsAction,
)
from depthcharge_tools.utils import OldCommand as Command

logger = logging.getLogger(__name__)


class Mkdepthcharge(Command):
    def __init__(self, name="mkdepthcharge", parent=None):
        super().__init__(name, parent)

        self._fit_options = self._parser.add_argument_group(
            title="FIT image options",
        )
        self._init_fit_options(self._fit_options)

        self._vboot_options = self._parser.add_argument_group(
            title="Depthcharge image options",
        )
        self._init_vboot_options(self._vboot_options)

    def __call__(
        self,
        arch=None,
        bootloader=None,
        cmdline=None,
        compress=None,
        devkeys=None,
        dtbs=None,
        image_format=None,
        initramfs=None,
        kern_guid=None,
        keyblock=None,
        name=None,
        output=None,
        signprivate=None,
        vmlinuz=None,
    ):
        # Normalize input arguments
        if vmlinuz is not None:
            vmlinuz = Path(vmlinuz).resolve()
            logger.info("Using vmlinuz: '{}'.".format(vmlinuz))
        else:
            msg = "vmlinuz argument is required."
            raise ValueError(msg)

        if initramfs is not None:
            initramfs = Path(initramfs).resolve()
            logger.info("Using initramfs: '{}'.".format(initramfs))

        if dtbs is not None:
            dtbs = [Path(dtb).resolve() for dtb in dtbs]
            for dtb in dtbs:
                logger.info("Using dtb: '{}'.".format(dtb))
        else:
            dtbs = []

        if bootloader is not None:
            bootloader = Path(bootloader).resolve()

        if devkeys is not None:
            devkeys = Path(devkeys).resolve()

        if signprivate is not None:
            signprivate = Path(signprivate).resolve()

        if keyblock is not None:
            keyblock = Path(keyblock).resolve()

        # We should be able to make an image for other architectures, but
        # the default should be this machine's.
        if arch is None:
            arch = Architecture(platform.machine())
            logger.info("Assuming CPU architecture '{}'.".format(arch))
        else:
            arch = Architecture(arch)

        # Default to architecture-specific formats.
        if image_format is None:
            if arch in Architecture.arm:
                image_format = "fit"
            elif arch in Architecture.x86:
                image_format = "zimage"
            logger.info("Assuming image format '{}'.".format(image_format))

        if image_format == "fit":
            # We need to pass "-C none" to mkimage or it assumes gzip.
            if compress is None:
                compress = "none"

            # If we don't pass "-n <name>" to mkimage, the kernel image
            # description is left blank. Other images get "unavailable"
            # as their description, so it looks better if we match that.
            if name is None:
                name = "unavailable"

        # If the cmdline is empty vbutil_kernel returns an error. We can use
        # "--" instead of putting a newline or a space into the cmdline.
        if cmdline is None:
            cmdline = "--"
        elif isinstance(cmdline, list):
            cmdline = " ".join(cmdline)

        # The firmware replaces any '%U' in the kernel cmdline with the
        # PARTUUID of the partition it booted from. Chrome OS uses
        # kern_guid=%U in their cmdline and it's useful information, so
        # prepend it to cmdline.
        if (kern_guid is None) or kern_guid:
            cmdline = " ".join(("kern_guid=%U", cmdline))

        # Default to distro-specific paths for necessary files.
        if keyblock is None and signprivate is None:
            if devkeys is not None:
                logger.info(
                    "Searching for keyblock and signprivate in dir '{}'."
                    .format(devkeys)
                )
                _, keyblock, signprivate, _ = vboot_keys(devkeys)
            else:
                logger.info("Searching for keyblock and signprivate.")
                devkeys, keyblock, signprivate, _ = vboot_keys()

        elif keyblock is not None and signprivate is not None:
            pass

        elif keyblock is None:
            d = devkeys or signprivate.parent
            logger.info("Searching for keyblock in dir '{}'.".format(d))
            devkeys, keyblock, _, _ = vboot_keys(d)

        elif signprivate is None:
            logger.info("Searching for signprivate in dir '{}'.".format(d))
            devkeys, _, signprivate, _ = vboot_keys(d)

        # We might still not have the vboot keys after all that.
        if keyblock is not None:
            logger.info("Using keyblock file '{}'.".format(keyblock))
        else:
            msg = "Couldn't find a usable keyblock file."
            raise ValueError(msg)

        if signprivate is not None:
            logger.info("Using signprivate file '{}'.".format(signprivate))
        else:
            msg = "Couldn't find a usable signprivate file."
            raise ValueError(msg)

        # Check incompatible combinations
        if image_format == "zimage":
            if compress is not None:
                msg = "compress argument not supported with zimage format."
                raise ValueError(msg)
            if name is not None:
                msg = "name argument not supported with zimage format."
                raise ValueError(msg)
            if initramfs is not None:
                msg = "Initramfs image not supported with zimage format."
                raise ValueError(msg)
            if dtbs:
                msg = "Device tree files not supported with zimage format."
                raise ValueError(msg)

        # Output path is obviously required
        if output is None:
            msg = "output argument is required."
            raise ValueError(msg)

        with TemporaryDirectory(prefix="mkdepthcharge-") as tmpdir:
            logger.debug("Working in temp dir '{}'.".format(tmpdir))

            # mkimage can't open files when they are read-only for some
            # reason. Copy them into a temp dir in fear of modifying the
            # originals.
            vmlinuz = vmlinuz.copy_to(tmpdir)
            if initramfs is not None:
                initramfs = initramfs.copy_to(tmpdir)
            dtbs = [dtb.copy_to(tmpdir) for dtb in dtbs]

            # We can add write permissions after we copy the files to temp.
            vmlinuz.chmod(0o755)
            if initramfs is not None:
                initramfs.chmod(0o755)
            for dtb in dtbs:
                dtb.chmod(0o755)

            # Debian packs the arm64 kernel uncompressed, but the bindeb-pkg
            # kernel target packs it as gzip.
            if vmlinuz.is_gzip():
                logger.info("Kernel is gzip compressed, decompressing.")
                vmlinuz = vmlinuz.gunzip()

            # Depthcharge on arm64 with FIT supports these two compressions.
            if compress == "lz4":
                logger.info("Compressing kernel with lz4.")
                vmlinuz = vmlinuz.lz4()
            elif compress == "lzma":
                logger.info("Compressing kernel with lzma.")
                vmlinuz = vmlinuz.lzma()
            elif compress is not None and compress != "none":
                fmt = "Compression type '{}' is not supported."
                msg = fmt.format(compress)
                raise ValueError(msg)

            # vbutil_kernel --config argument wants cmdline as a file.
            cmdline_file = tmpdir / "kernel.args"
            cmdline_file.write_text(cmdline)

            # vbutil_kernel --bootloader argument is mandatory, but it's
            # contents don't matter at least on arm systems.
            if bootloader is not None:
                bootloader = bootloader.copy_to(tmpdir)
            else:
                bootloader = tmpdir / "bootloader.bin"
                bootloader.write_bytes(bytes(512))
                logger.info("Using dummy file for bootloader.")

            if image_format == "fit":
                fit_image = tmpdir / "depthcharge.fit"

                initramfs_args = []
                if initramfs is not None:
                    initramfs_args += ["-i", initramfs]

                dtb_args = []
                for dtb in dtbs:
                    dtb_args += ["-b", dtb]

                logger.info("Packing files as FIT image:")
                proc = mkimage(
                    "-f", "auto",
                    "-A", arch.mkimage,
                    "-O", "linux",
                    "-C", compress,
                    "-n", name,
                    *initramfs_args,
                    *dtb_args,
                    "-d", vmlinuz,
                    fit_image,
                )
                logger.info(proc.stdout)

                logger.info("Using FIT image as vboot kernel.")
                vmlinuz_vboot = fit_image

            elif image_format == "zimage":
                logger.info("Using vmlinuz file as vboot kernel.")
                vmlinuz_vboot = vmlinuz

            logger.info("Packing files as depthcharge image.")
            proc = vbutil_kernel(
                "--version", "1",
                "--arch", arch.vboot,
                "--vmlinuz", vmlinuz_vboot,
                "--config", cmdline_file,
                "--bootloader", bootloader,
                "--keyblock", keyblock,
                "--signprivate", signprivate,
                "--pack", output,
            )
            logger.info(proc.stdout)

            logger.info("Verifying built depthcharge image:")
            proc = vbutil_kernel("--verify", output)
            logger.info(proc.stdout)

    def _init_parser(self):
        return super()._init_parser(
            description="Build boot images for the ChromeOS bootloader.",
            usage="%(prog)s [options] -o FILE [--] vmlinuz [initramfs] [dtb ...]",
            add_help=False,
        )

    def _init_arguments(self, arguments):
        class InputFileAction(MixedArgumentsAction):
            pass

        arguments.add_argument(
            "vmlinuz",
            action=InputFileAction,
            select=Path.is_vmlinuz,
            type=Path,
            help="Kernel executable",
        )
        arguments.add_argument(
            "initramfs",
            nargs="?",
            action=InputFileAction,
            select=Path.is_initramfs,
            type=Path,
            help="Ramdisk image",
        )
        arguments.add_argument(
            "dtbs",
            metavar="dtb",
            nargs="*",
            default=[],
            action=InputFileAction,
            select=Path.is_dtb,
            type=Path,
            help="Device-tree binary file",
        )

    def _init_options(self, options):
        options.add_argument(
            "-h", "--help",
            action='help',
            help="Show this help message.",
        )
        options.add_argument(
            "--version",
            action='version',
            version="depthcharge-tools %(prog)s {}".format(__version__),
            help="Print program version.",
        )
        options.add_argument(
            "-v", "--verbose",
            dest=argparse.SUPPRESS,
            action=LoggingLevelAction,
            level="-10",
            help="Print more detailed output.",
        )
        options.add_argument(
            "-o", "--output",
            metavar="FILE",
            action='store',
            required=True,
            type=Path,
            help="Write resulting image to FILE.",
        )
        options.add_argument(
            "-A", "--arch",
            metavar="ARCH",
            action='store',
            choices=Architecture.all,
            type=Architecture,
            help="Architecture to build for.",
        )
        options.add_argument(
            "--format",
            dest="image_format",
            metavar="FORMAT",
            action='store',
            choices=["fit", "zimage"],
            help="Kernel image format to use.",
        )

    def _init_fit_options(self, fit_options):
        fit_options.add_argument(
            "-C", "--compress",
            metavar="TYPE",
            action='store',
            choices=["none", "lz4", "lzma"],
            help="Compress vmlinuz file before packing.",
        )
        fit_options.add_argument(
            "-n", "--name",
            metavar="DESC",
            action='store',
            help="Description of vmlinuz to put in the FIT.",
        )

    def _init_vboot_options(self, vboot_options):
        vboot_options.add_argument(
            "-c", "--cmdline",
            metavar="CMD",
            action='append',
            help="Command-line parameters for the kernel.",
        )
        vboot_options.add_argument(
            "--no-kern-guid",
            dest='kern_guid',
            action='store_false',
            help="Don't prepend kern_guid=%%U to the cmdline.",
        )
        vboot_options.add_argument(
            "--bootloader",
            metavar="FILE",
            action='store',
            type=Path,
            help="Bootloader stub binary to use.",
        )
        vboot_options.add_argument(
            "--devkeys",
            metavar="DIR",
            action='store',
            type=Path,
            help="Directory containing developer keys to use.",
        )
        vboot_options.add_argument(
            "--keyblock",
            metavar="FILE",
            action='store',
            type=Path,
            help="The key block file (.keyblock).",
        )
        vboot_options.add_argument(
            "--signprivate",
            metavar="FILE",
            action='store',
            type=Path,
            help="Private key (.vbprivk) to sign the image.",
        )


mkdepthcharge = Mkdepthcharge()


if __name__ == "__main__":
    mkdepthcharge._main()
