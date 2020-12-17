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
    Command,
    LoggingLevelAction,
    MixedArgumentsAction,
)

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
        # Use helper class for input files
        if vmlinuz is not None:
            vmlinuz = Path(vmlinuz)
        if initramfs is not None:
            initramfs = Path(initramfs)
        if dtbs is not None:
            dtbs = [Path(dtb) for dtb in dtbs]
        if bootloader is not None:
            bootloader = Path(bootloader)
        if devkeys is not None:
            devkeys = Path(devkeys)
        if signprivate is not None:
            signprivate = Path(signprivate)
        if keyblock is not None:
            keyblock = Path(keyblock)

        # We should be able to make an image for other architectures, but
        # the default should be this machine's.
        if arch is None:
            arch = Architecture(platform.machine())
        else:
            arch = Architecture(arch)

        # Default to architecture-specific formats.
        if image_format is None:
            if arch in Architecture.arm:
                image_format = "fit"
            elif arch in Architecture.x86:
                image_format = "zimage"

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
                _, keyblock, signprivate, _ = vboot_keys(devkeys)
            else:
                devkeys, keyblock, signprivate, _ = vboot_keys()

        elif keyblock is not None and signprivate is not None:
            pass

        elif signprivate is not None:
            devkeys, keyblock, _, _ = vboot_keys(
                devkeys or signprivate.parent,
            )

        elif keyblock is not None:
            devkeys, _, signprivate, _ = vboot_keys(
                devkeys or keyblock.parent,
            )

        # Check for required arguments
        if vmlinuz is None:
            msg = "vmlinuz argument is required."
            raise ValueError(msg)
        if output is None:
            msg = "output argument is required."
            raise ValueError(msg)
        if keyblock is None:
            msg = "Couldn't find a usable keyblock file."
            raise ValueError(msg)
        if signprivate is None:
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

        with TemporaryDirectory(prefix="mkdepthcharge-") as tmpdir:
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
                vmlinuz = vmlinuz.gunzip()

            # Depthcharge on arm64 with FIT supports these two compressions.
            if compress == "lz4":
                vmlinuz = vmlinuz.lz4()
            elif compress == "lzma":
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

            if image_format == "fit":
                fit_image = tmpdir / "depthcharge.fit"

                initramfs_args = []
                if initramfs is not None:
                    initramfs_args += ["-i", initramfs]

                dtb_args = []
                for dtb in dtbs:
                    dtb_args += ["-b", dtb]

                mkimage(
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

                vmlinuz_vboot = fit_image

            elif image_format == "zimage":
                vmlinuz_vboot = vmlinuz

            vbutil_kernel(
                "--version", "1",
                "--arch", arch.vboot,
                "--vmlinuz", vmlinuz_vboot,
                "--config", cmdline_file,
                "--bootloader", bootloader,
                "--keyblock", keyblock,
                "--signprivate", signprivate,
                "--pack", output,
            )

            vbutil_kernel("--verify", output)

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
