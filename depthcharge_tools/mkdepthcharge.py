#! /usr/bin/env python3

import argparse
import logging
import os
import platform
import subprocess
import sys
import tempfile

from pathlib import Path

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
)
from depthcharge_tools.utils.pathlib import (
    copy,
    is_gzip,
    gunzip,
    lz4,
    lzma,
)
from depthcharge_tools.utils.platform import (
    Architecture,
    vboot_keys,
)
from depthcharge_tools.utils.subprocess import (
    mkimage,
    vbutil_kernel,
    gzip as gzip_runner,
)


class mkdepthcharge(
    Command,
    prog="mkdepthcharge",
    usage="%(prog)s [options] -o FILE [--] [VMLINUZ] [INITRAMFS] [DTB ...]",
    add_help=False,
):
    """Build boot images for the ChromeOS bootloader."""

    logger = logging.getLogger(__name__)

    @Group
    def input_files(self):
        """Input files"""

    @input_files.add
    @Argument(help=argparse.SUPPRESS)
    def files(self, *files):
        vmlinuz = []
        initramfs = []
        dtbs = []

        files = [Path(f).resolve() for f in files]

        for f in files:
            with f.open("rb") as f_:
                head = f_.read(4096)

            # Partially decompress gzip files to run detection on content
            if head.startswith(b"\x1f\x8b"):
                try:
                    gzip_runner.decompress(head, subprocess.PIPE)
                except subprocess.CalledProcessError as err:
                    if err.output:
                        head = err.output

            # Portable Executable and ELF files
            if head.startswith(b"MZ") or head.startswith(b"ELF"):
                vmlinuz.append(f)

            # Cpio files
            elif (
                head.startswith(b"070701")
                or head.startswith(b"070702")
                or head.startswith(b"070707")
            ):
                initramfs.append(f)

            # Device-tree blobs
            elif head.startswith(b"\xd0\x0d\xfe\xed"):
                dtbs.append(f)

            # Failed to detect, assume in the order in usage string
            elif len(vmlinuz) == 0:
                vmlinuz.append(f)
            elif len(initramfs) == 0:
                initramfs.append(f)
            else:
                dtbs.append(f)

        return {
            "vmlinuz": vmlinuz,
            "initramfs": initramfs,
            "dtbs": dtbs,
        }

    @input_files.add
    @Argument("-d", "--vmlinuz", nargs=1)
    def vmlinuz(self, vmlinuz=None):
        """Kernel executable"""
        files = self.files["vmlinuz"]

        if vmlinuz is not None:
            files = [Path(vmlinuz).resolve(), *files]

        if len(files) == 0:
            raise ValueError(
                "vmlinuz argument is required."
            )

        elif len(files) > 1:
            raise ValueError(
                "Can't build with multiple kernels"
            )

        vmlinuz = files[0]

        return vmlinuz

    @input_files.add
    @Argument("-i", "--initramfs", nargs=1)
    def initramfs(self, initramfs=None):
        """Ramdisk image"""
        files = self.files["initramfs"]

        if initramfs is not None:
            files = [Path(initramfs).resolve(), *files]

        if len(files) > 1:
            raise ValueError(
                "Can't build with multiple initramfs"
            )

        if files:
            initramfs = files[0]
        else:
            initramfs = None

        return initramfs

    @input_files.add
    @Argument("-b", "--dtbs", metavar="DTB", nargs="+")
    def dtbs(self, *dtbs):
        """Device-tree binary file"""
        files = self.files["dtbs"]

        if dtbs:
            dtbs = [Path(dtb).resolve() for dtb in dtbs]

        dtbs = [*dtbs, *files]

        return dtbs

    @Group
    def options(self):
        """Options"""
        # Check incompatible combinations
        if self.image_format == "zimage":
            if self.compress not in (None, "none"):
                raise ValueError(
                    "Compress argument not supported with zimage format."
                )
            if self.name is not None:
                raise ValueError(
                    "Name argument not supported with zimage format."
                )
            if self.initramfs is not None:
                raise ValueError(
                    "Initramfs image not supported with zimage format."
                )
            if self.dtbs:
                raise ValueError(
                    "Device tree files not supported with zimage format."
                )

    @options.add
    @Argument("-h", "--help", action="help")
    def print_help(self):
        """Show this help message."""
        # type(self).parser.print_help()

    @options.add
    @Argument(
        "-V", "--version",
        action="version",
        version="depthcharge-tools %(prog)s {}".format(__version__),
    )
    def version(self):
        """Print program version."""
        return type(self).version.version % {"prog": type(self).prog}

    @options.add
    @Argument("-v", "--verbose", count=True)
    def verbosity(self, verbosity=0):
        """Print more detailed output."""
        level = logging.WARNING - int(verbosity) * 10
        self.logger.setLevel(level)
        return verbosity

    @options.add
    @Argument("-o", "--output", required=True)
    def output(self, file_):
        """Write resulting image to FILE."""

        # Output path is obviously required
        if file_ is None:
            raise ValueError(
                "Output argument is required."
            )

        return Path(file_).resolve()

    @options.add
    @Argument("--tmpdir", nargs=1)
    def tmpdir(self, dir_=None):
        """Directory to keep temporary files."""
        if dir_ is None:
            dir_ = tempfile.TemporaryDirectory(
                prefix="mkdepthcharge-",
            )
            dir_ = self.exitstack.enter_context(dir_)

        dir_ = Path(dir_)
        os.makedirs(dir_, exist_ok=True)

        self.logger.debug("Working in temp dir '{}'.".format(dir_))

        return dir_

    @options.add
    @Argument("-A", "--arch", nargs=1)
    def arch(self, arch=None):
        """Architecture to build for."""

        # We should be able to make an image for other architectures, but
        # the default should be this machine's.
        if arch is None:
            arch = Architecture(platform.machine())
            self.logger.info("Assuming CPU architecture '{}'.".format(arch))
        elif arch not in Architecture.all:
            raise ValueError(
                "Can't build images for unknown architecture '{}'"
                .format(arch)
            )

        return Architecture(arch)

    @options.add
    @Argument("--format", nargs=1)
    def image_format(self, format_=None):
        """Kernel image format to use."""

        # Default to architecture-specific formats.
        if format_ is None:
            if self.arch in Architecture.arm:
                format_ = "fit"
            elif self.arch in Architecture.x86:
                format_ = "zimage"
            self.logger.info("Assuming image format '{}'.".format(format_))

        if format_ not in ("fit", "zimage"):
            raise ValueError(
                "Can't build images for unknown image format '{}'"
                .format(format_)
            )

        return format_

    @Group
    def fit_options(self):
        """FIT image options"""

    @fit_options.add
    @Argument("-C", "--compress", nargs=1)
    def compress(self, type_=None):
        """Compress vmlinuz file before packing."""

        # We need to pass "-C none" to mkimage or it assumes gzip.
        if type_ is None and self.image_format == "fit":
            type_ = "none"

        if type_ not in (None, "none", "lz4", "lzma"):
            raise ValueError(
                "Compression type '{}' is not supported."
                .format(type_)
            )

        return type_

    @fit_options.add
    @Argument("-n", "--name", nargs=1)
    def name(self, desc=None):
        """Description of vmlinuz to put in the FIT."""

        # If we don't pass "-n <name>" to mkimage, the kernel image
        # description is left blank. Other images get "unavailable"
        # as their description, so it looks better if we match that.
        if desc is None and self.image_format == "fit":
            desc = "unavailable"

        return desc

    @Group
    def vboot_options(self):
        """Depthcharge image options"""

        keydirs = []
        if self.keydir is not None:
            keydirs += [self.keydir]

        # If any of the arguments are given, search nearby for others
        if self.keyblock is not None:
            keydirs += [self.keyblock.parent]
        if self.signprivate is not None:
            keydirs += [self.signprivate.parent]
        if self.signpubkey is not None:
            keydirs += [self.signpubkey.parent]

        for d in sorted(set(keydirs), key=keydirs.index):
            self.logger.info(
                "Searching '{}' for vboot keys."
                .format(d)
            )

        # Defaults to distro-specific paths for necessary files.
        keydir, keyblock, signprivate, signpubkey = vboot_keys(*keydirs)

        if keydir:
            self.logger.info(
                "Defaulting to keys from '{}' for missing arguments."
                .format(keydir)
            )

        if self.keyblock is None:
            self.keyblock = keyblock
        if self.signprivate is None:
            self.signprivate = signprivate
        if self.signpubkey is None:
            self.signpubkey = signpubkey

        # We might still not have the vboot keys after all that.
        if self.keyblock is None:
            raise ValueError(
                "Couldn't find a usable keyblock file."
            )
        elif not self.keyblock.is_file():
            raise ValueError(
                "Keyblock file '{}' does not exist."
                .format(self.keyblock)
            )
        else:
            self.logger.info(
                "Using keyblock file '{}'."
                .format(self.keyblock)
            )

        if self.signprivate is None:
            raise ValueError(
                "Couldn't find a usable signprivate file."
            )
        elif not self.signprivate.is_file():
            raise ValueError(
                "Signprivate file '{}' does not exist."
                .format(self.keyblock)
            )
        else:
            self.logger.info(
                "Using signprivate file '{}'."
                .format(self.signprivate)
            )

        if self.signpubkey is None:
            self.logger.warn(
                "Couldn't find a usable signpubkey file."
            )
        elif not self.signpubkey.is_file():
            self.logger.warn(
                "Signpubkey file '{}' does not exist."
                .format(self.keyblock)
            )
            self.signpubkey = None
        else:
            self.logger.info(
                "Using signpubkey file '{}'."
                .format(self.signpubkey)
            )

    @vboot_options.add
    @Argument("-c", "--cmdline", append=True, nargs="+")
    def cmdline(self, *cmd):
        """Command-line parameters for the kernel."""

        # If the cmdline is empty vbutil_kernel returns an error. We can use
        # "--" instead of putting a newline or a space into the cmdline.
        if len(cmd) == 0:
            cmdline = "--"
        elif len(cmd) == 1 and isinstance(cmd[0], str):
            cmdline = cmd[0]
        elif isinstance(cmd, (list, tuple)):
            cmdline = " ".join(cmd)

        # The firmware replaces any '%U' in the kernel cmdline with the
        # PARTUUID of the partition it booted from. Chrome OS uses
        # kern_guid=%U in their cmdline and it's useful information, so
        # prepend it to cmdline.
        if (self.kern_guid is None) or self.kern_guid:
            cmdline = " ".join(("kern_guid=%U", cmdline))

        return cmdline

    @vboot_options.add
    @Argument("--no-kern-guid", kern_guid=False)
    def kern_guid(self, kern_guid=True):
        """Don't prepend kern_guid=%%U to the cmdline."""
        return kern_guid

    @vboot_options.add
    @Argument("--bootloader", nargs=1)
    def bootloader(self, file_=None):
        """Bootloader stub binary to use."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        return file_

    @vboot_options.add
    @Argument("--keydir")
    def keydir(self, dir_):
        """Directory containing vboot keys to use."""
        if dir_ is not None:
            dir_ = Path(dir_).resolve()

        return dir_

    @vboot_options.add
    @Argument("--keyblock")
    def keyblock(self, file_):
        """The key block file (.keyblock)."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        return file_

    @vboot_options.add
    @Argument("--signprivate")
    def signprivate(self, file_):
        """Private key (.vbprivk) to sign the image."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        return file_

    @vboot_options.add
    @Argument("--signpubkey")
    def signpubkey(self, file_):
        """Public key (.vbpubk) to verify the image."""
        if file_ is not None:
            file_ = Path(file_).resolve()

        return file_

    def __call__(self):
        vmlinuz = self.vmlinuz
        initramfs = self.initramfs
        dtbs = self.dtbs
        tmpdir = self.tmpdir

        self.logger.info(
            "Using vmlinuz: '{}'."
            .format(vmlinuz)
        )
        if initramfs is not None:
            self.logger.info(
                "Using initramfs: '{}'."
                .format(initramfs)
            )
        for dtb in dtbs:
            self.logger.info(
                "Using dtb: '{}'."
                .format(dtb)
            )


        # mkimage can't open files when they are read-only for some
        # reason. Copy them into a temp dir in fear of modifying the
        # originals.
        vmlinuz = copy(vmlinuz, tmpdir)
        if initramfs is not None:
            initramfs = copy(initramfs, tmpdir)
        dtbs = [copy(dtb, tmpdir) for dtb in dtbs]

        # We can add write permissions after we copy the files to temp.
        vmlinuz.chmod(0o755)
        if initramfs is not None:
            initramfs.chmod(0o755)
        for dtb in dtbs:
            dtb.chmod(0o755)

        # Debian packs the arm64 kernel uncompressed, but the bindeb-pkg
        # kernel target packs it as gzip.
        if is_gzip(vmlinuz):
            self.logger.info("Kernel is gzip compressed, decompressing.")
            vmlinuz = gunzip(vmlinuz)

        # Depthcharge on arm64 with FIT supports these two compressions.
        if self.compress == "lz4":
            self.logger.info("Compressing kernel with lz4.")
            vmlinuz = lz4(vmlinuz)
        elif self.compress == "lzma":
            self.logger.info("Compressing kernel with lzma.")
            vmlinuz = lzma(vmlinuz)
        elif self.compress not in (None, "none"):
            fmt = "Compression type '{}' is not supported."
            msg = fmt.format(compress)
            raise ValueError(msg)

        # vbutil_kernel --config argument wants cmdline as a file.
        cmdline_file = tmpdir / "kernel.args"
        cmdline_file.write_text(self.cmdline)

        # vbutil_kernel --bootloader argument is mandatory, but it's
        # contents don't matter at least on arm systems.
        if self.bootloader is not None:
            bootloader = copy(bootloader, tmpdir)
        else:
            bootloader = tmpdir / "bootloader.bin"
            bootloader.write_bytes(bytes(512))
            self.logger.info("Using dummy file for bootloader.")

        if self.image_format == "fit":
            fit_image = tmpdir / "depthcharge.fit"

            initramfs_args = []
            if initramfs is not None:
                initramfs_args += ["-i", initramfs]

            dtb_args = []
            for dtb in dtbs:
                dtb_args += ["-b", dtb]

            self.logger.info("Packing files as FIT image:")
            proc = mkimage(
                "-f", "auto",
                "-A", self.arch.mkimage,
                "-O", "linux",
                "-C", self.compress,
                "-n", self.name,
                *initramfs_args,
                *dtb_args,
                "-d", vmlinuz,
                fit_image,
            )
            self.logger.info(proc.stdout)

            self.logger.info("Using FIT image as vboot kernel.")
            vmlinuz_vboot = fit_image

        elif self.image_format == "zimage":
            self.logger.info("Using vmlinuz file as vboot kernel.")
            vmlinuz_vboot = vmlinuz

        self.logger.info("Packing files as depthcharge image.")
        proc = vbutil_kernel(
            "--version", "1",
            "--arch", self.arch.vboot,
            "--vmlinuz", vmlinuz_vboot,
            "--config", cmdline_file,
            "--bootloader", bootloader,
            "--keyblock", self.keyblock,
            "--signprivate", self.signprivate,
            "--pack", self.output,
        )
        self.logger.info(proc.stdout)

        self.logger.info("Verifying built depthcharge image:")
        signpubkey_args = []
        if self.signpubkey is not None:
            signpubkey_args += ["--signpubkey", self.signpubkey]

        proc = vbutil_kernel(
            "--verify", self.output,
            *signpubkey_args,
        )
        self.logger.info(proc.stdout)

        return self.output


if __name__ == "__main__":
    mkdepthcharge.main()
