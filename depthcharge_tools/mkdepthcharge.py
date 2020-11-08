#! /usr/bin/env python3

import argparse
import logging
import pathlib
import platform
import shutil
import subprocess
import sys
import tempfile

from depthcharge_tools import __version__
from depthcharge_tools.utils import DemuxAction

logger = logging.getLogger(__name__)


def main(*argv):
    args = parse_args(*argv)

    with tempfile.TemporaryDirectory(prefix="mkdepthcharge-") as tmpdir:
        tmpdir = pathlib.Path(tmpdir)

        vmlinuz = tmpdir / args.vmlinuz.name
        shutil.copyfile(args.vmlinuz, vmlinuz)
        args.vmlinuz = vmlinuz

        if is_gzip(args.vmlinuz):
            if args.vmlinuz.name.endswith(".gz"):
                vmlinuz_ungzip = tmpdir / args.vmlinuz.name[:-3]
            else:
                vmlinuz_ungzip = tmpdir / (args.vmlinuz.name + ".gunzip")
            ungzip(args.vmlinuz, vmlinuz_ungzip)
            args.vmlinuz = vmlinuz_ungzip

        if args.initramfs is not None:
            initramfs = tmpdir / args.initramfs.name
            shutil.copyfile(args.initramfs, initramfs)
            args.initramfs = initramfs

        dtb = [tmpdir / d.name for d in args.dtb]
        for src, dest in zip(args.dtb, dtb):
            shutil.copyfile(src, dest)
        args.dtb = dtb

        if args.compress == "lz4":
            vmlinuz_lz4 = tmpdir / (args.vmlinuz.name + ".lz4")
            lz4(args.vmlinuz, vmlinuz_lz4)
            args.vmlinuz = vmlinuz_lz4
        elif args.compress == "lzma":
            vmlinuz_lzma = tmpdir / (args.vmlinuz.name + ".lzma")
            lzma(args.vmlinuz, vmlinuz_lzma)
            args.vmlinuz = vmlinuz_lzma

        if args.kern_guid:
            args.cmdline.insert(0, "kern_guid=%U")
        args.cmdline = " ".join(args.cmdline)
        cmdline_file = tmpdir / "kernel.args"
        cmdline_file.write_text(args.cmdline)

        if args.bootloader is not None:
            bootloader = tmpdir / args.bootloader.name
            shutil.copyfile(args.bootloader, bootloader)
            args.bootloader = bootloader
        else:
            bootloader = tmpdir / "bootloader.bin"
            bootloader.write_bytes(bytes(512))
            args.bootloader = bootloader

        if args.arch == "arm":
            mkimage_arch = "arm"
            vboot_arch = "arm"
        elif args.arch in ("arm64", "aarch64"):
            mkimage_arch = "arm64"
            vboot_arch = "aarch64"
        elif args.arch in ("i386", "x86"):
            mkimage_arch = "x86"
            vboot_arch = "x86"
        elif args.arch in ("x86_64", "amd64"):
            mkimage_arch = "x86_64"
            vboot_arch = "amd64"

        if args.image_format == "fit":
            fit_image = tmpdir / "depthcharge.fit"
            mkimage_cmd = [
                "mkimage",
                "-f", "auto",
                "-A", mkimage_arch,
                "-O", "linux",
                "-C", args.compress,
                "-n", args.name,
                "-d", args.vmlinuz,
            ]
            if args.initramfs:
                mkimage_cmd.extend(["-i", args.initramfs])
            for dtb in args.dtb:
                mkimage_cmd.extend(["-b", dtb])
            mkimage_cmd.append(fit_image)
            proc = subprocess.run(mkimage_cmd)
            proc.check_returncode()
            vboot_vmlinuz = fit_image

        elif args.image_format == "zimage":
            vboot_vmlinuz = fit_image

        vboot_cmd = [
            "futility", "vbutil_kernel",
            "--version", "1",
            "--arch", vboot_arch,
            "--vmlinuz", vboot_vmlinuz,
            "--config", cmdline_file,
            "--bootloader", args.bootloader,
            "--keyblock", args.keyblock,
            "--signprivate", args.signprivate,
            "--pack", args.output
        ]
        proc = subprocess.run(vboot_cmd)
        proc.check_returncode()

        verify_cmd = [
            "futility", "vbutil_kernel",
            "--verify", args.output,
        ]


def is_gzip(path):
    proc = subprocess.run(["gzip", "-t", path])
    return proc.returncode == 0


def gunzip(src, dest):
    with src.open() as s:
        with dest.open('w') as d:
            proc = subprocess.run(["gzip", "-d"], stdin=s, stdout=d)
    proc.check_returncode()


def lz4(src, dest):
    with src.open() as s:
        with dest.open('w') as d:
            proc = subprocess.run(["lz4", "-z", "-9"], stdin=s, stdout=d)
    proc.check_returncode()


def lzma(src, dest):
    with src.open() as s:
        with dest.open('w') as d:
            proc = subprocess.run(["lzma", "-z"], stdin=s, stdout=d)
    proc.check_returncode()


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



def parse_args(*argv):
    parser = argparse.ArgumentParser(
        description="Build boot images for the ChromeOS bootloader.",
        usage="%(prog)s [options] -o FILE [--] vmlinuz [initramfs] [dtb ...]",
        add_help=False,
    )

    class InputFileAction(DemuxAction):
        pass

    input_files = parser.add_argument_group(
        title="Input files",
    )
    input_files.add_argument(
        "vmlinuz",
        action=InputFileAction,
        select=is_vmlinuz,
        type=pathlib.Path,
        help="Kernel executable",
    )
    input_files.add_argument(
        "initramfs",
        nargs="?",
        action=InputFileAction,
        select=is_initramfs,
        type=pathlib.Path,
        help="Ramdisk image",
    )
    input_files.add_argument(
        "dtb",
        nargs="*",
        default=[],
        action=InputFileAction,
        select=is_dtb,
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
