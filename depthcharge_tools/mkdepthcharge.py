#! /usr/bin/env python3

from depthcharge_tools import __version__

import argparse
import logging
import pathlib
import sys

logger = logging.getLogger(__name__)


def main(*argv):
    args = parse_args(*argv)
    print(args)


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
        type=pathlib.Path,
        help="Kernel executable",
    )
    input_files.add_argument(
        "initramfs",
        nargs="?",
        type=pathlib.Path,
        help="Ramdisk image",
    )
    input_files.add_argument(
        "dtb",
        nargs="*",
        default=[],
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
        choices=["arm", "arm64", "aarch64", "x86", "x86_64", "amd64"],
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
        help="Compress vmlinuz file before packing.",
    )
    fit_options.add_argument(
        "-n", "--name",
        metavar="DESC",
        action='store',
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

    return parser.parse_args(*argv[1:])


if __name__ == "__main__":
    main(sys.argv)
