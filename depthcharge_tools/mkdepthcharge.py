#! /usr/bin/env python3

from depthcharge_tools import __version__

import argparse
import logging
import pathlib
import platform
import sys

logger = logging.getLogger(__name__)


def main(*argv):
    args = parse_args(*argv)
    print(args)


def is_vmlinuz(path):
    return any((
        "vmlinuz" in path.name,
        "vmlinux" in path.name,
        "linux" in path.name,
        "Image" in path.name,
        "kernel" in path.name,
    ))


def is_initramfs(path):
    return any((
        "initrd" in path.name,
        "initramfs" in path.name,
        "cpio" in path.name,
    ))


def is_dtb(path):
    return any((
        "dtb" in path.name,
    ))


class InputFileAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, pathlib.Path):
            values = [values]
        elif values is None:
            return

        for path in list(values):
            if is_dtb(path):
                namespace.dtb.append(path)

            elif is_initramfs(path):
                if namespace.initramfs is not None:
                    fmt = "Cannot have multiple initramfs args '{}' and '{}'."
                    msg = fmt.format(namespace.initramfs, path)
                    parser.error(msg)
                namespace.initramfs = path

            elif is_vmlinuz(path):
                if namespace.vmlinuz is not None:
                    fmt = "Cannot have multiple vmlinuz args '{}' and '{}'."
                    msg = fmt.format(namespace.vmlinuz, path)
                    parser.error(msg)
                namespace.vmlinuz = path

            elif namespace.vmlinuz is None:
                namespace.vmlinuz = path
            elif namespace.initramfs is None:
                namespace.initramfs = path
            else:
                namespace.dtb.append(path)


def parse_args(*argv):
    parser = argparse.ArgumentParser(
        description="Build boot images for the ChromeOS bootloader.",
        usage="%(prog)s [options] -o FILE [--] vmlinuz [initramfs] [dtb ...]",
        add_help=False,
    )

    input_files = parser.add_argument_group(
        title="Input files",
    )
    input_files.add_argument(
        "vmlinuz",
        action=InputFileAction,
        type=pathlib.Path,
        help="Kernel executable",
    )
    input_files.add_argument(
        "initramfs",
        nargs="?",
        action=InputFileAction,
        type=pathlib.Path,
        help="Ramdisk image",
    )
    input_files.add_argument(
        "dtb",
        nargs="*",
        default=[],
        action=InputFileAction,
        type=pathlib.Path,
        help="Device-tree binary file",
    )

    options = parser.add_argument_group(
        title="Options",
    )
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
        action='store_true',
        help="Print more detailed output.",
    )
    options.add_argument(
        "-o", "--output",
        metavar="FILE",
        action='store',
        required=True,
        type=pathlib.Path,
        help="Write resulting image to FILE.",
    )
    options.add_argument(
        "-A", "--arch",
        metavar="ARCH",
        action='store',
        choices=["arm", "arm64", "aarch64", "i386", "x86", "x86_64", "amd64"],
        default=platform.machine(),
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

    fit_options = parser.add_argument_group(
        title="FIT image options",
    )
    fit_options.add_argument(
        "-C", "--compress",
        metavar="TYPE",
        action='store',
        choices=["none", "lz4", "lzma"],
        default="none",
        help="Compress vmlinuz file before packing.",
    )
    fit_options.add_argument(
        "-n", "--name",
        metavar="DESC",
        action='store',
        default="unavailable",
        help="Description of vmlinuz to put in the FIT.",
    )

    vboot_options = parser.add_argument_group(
        title="Depthcharge image options",
    )
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
        type=pathlib.Path,
        help="Bootloader stub binary to use.",
    )
    vboot_options.add_argument(
        "--devkeys",
        metavar="DIR",
        action='store',
        type=pathlib.Path,
        help="Directory containing developer keys to use.",
    )
    vboot_options.add_argument(
        "--keyblock",
        metavar="FILE",
        action='store',
        type=pathlib.Path,
        help="The key block file (.keyblock).",
    )
    vboot_options.add_argument(
        "--signprivate",
        metavar="FILE",
        action='store',
        type=pathlib.Path,
        help="Private key (.vbprivk) to sign the image.",
    )

    args = parser.parse_args(*argv[1:])

    # Set defaults
    if args.image_format is None:
        if args.arch in ("arm", "arm64", "aarch64"):
            args.image_format = "fit"
        elif args.arch in ("i386", "x86", "x86_64", "amd64"):
            args.image_format = "zimage"

    if args.cmdline is None:
        args.cmdline = ["--"]

    if args.devkeys is None:
        if args.keyblock is None and args.signprivate is None:
            args.devkeys = pathlib.Path("/usr/share/vboot/devkeys")
        elif args.keyblock is not None and args.signprivate is not None:
            if args.keyblock.parent == args.signprivate.parent:
                args.devkeys = args.signprivate.parent
        elif args.signprivate is not None:
            args.devkeys = args.signprivate.parent
        elif args.keyblock is not None:
            args.devkeys = args.keyblock.parent

    if args.keyblock is None:
        args.keyblock = args.devkeys / "kernel.keyblock"
    if args.signprivate is None:
        args.signprivate = args.devkeys / "kernel_data_key.vbprivk"

    # Check incompatible combinations
    if args.image_format == "zimage":
        if args.compress != "none":
            msg = "--compress is incompatible with zimage format."
            parser.error(msg)
        if args.name != "unavailable":
            msg = "--name is incompatible with zimage format."
        if args.initramfs is not None:
            msg = "Initramfs image not supported with zimage format."
            parser.error(msg)
        if args.dtb:
            msg = "Device tree files not supported with zimage format."
            parser.error(msg)

    return args


if __name__ == "__main__":
    main(sys.argv)
