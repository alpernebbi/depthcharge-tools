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
    Argument,
    Group,
)

logger = logging.getLogger(__name__)


class mkdepthcharge(
    Command,
    prog="mkdepthcharge",
    usage="%(prog)s [options] -o FILE [--] VMLINUZ [INITRAMFS] [DTB ...]",
    add_help=False,
):
    """Build boot images for the ChromeOS bootloader."""

    @Group
    def input_files(self):
        """Input files"""
        vmlinuz = None
        initramfs = None
        dtbs = []

        for f in [self.vmlinuz, self.initramfs, *(self.dtbs or [])]:
            if f is None:
                pass

            elif f.is_vmlinuz():
                if vmlinuz is None:
                    vmlinuz = f
                else:
                    raise TypeError("Can't build with multiple kernels")

            elif f.is_initramfs():
                if initramfs is None:
                    initramfs = f
                else:
                    raise TypeError("Can't build with multiple initramfs")

            elif f.is_dtb():
                dtbs.append(f)

            elif vmlinuz is None:
                vmlinuz = f

            elif initramfs is None:
                initramfs = f

            else:
                dtbs.append(f)

        self.vmlinuz = vmlinuz
        self.initramfs = initramfs
        self.dtbs = dtbs

        if vmlinuz is not None:
            logger.info("Using vmlinuz: '{}'.".format(vmlinuz))
        else:
            msg = "vmlinuz argument is required."
            raise ValueError(msg)

        if initramfs is not None:
            logger.info("Using initramfs: '{}'.".format(initramfs))

        for dtb in dtbs:
            logger.info("Using dtb: '{}'.".format(dtb))

    @input_files.add
    @Argument
    def vmlinuz(self, vmlinuz):
        """Kernel executable"""
        if vmlinuz is not None:
            vmlinuz = Path(vmlinuz).resolve()

        return vmlinuz

    @input_files.add
    @Argument
    def initramfs(self, initramfs=None):
        """Ramdisk image"""
        if initramfs is not None:
            initramfs = Path(initramfs).resolve()

        return initramfs

    @input_files.add
    @Argument(metavar="DTB")
    def dtbs(self, *dtbs):
        """Device-tree binary file"""
        if dtbs is not None:
            dtbs = [Path(dtb).resolve() for dtb in dtbs]
        else:
            dtbs = []

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
    def verbosity(self, verbosity):
        """Print more detailed output."""
        logger = logging.getLogger()
        level = logger.getEffectiveLevel()
        level = level - int(verbosity) * 10
        logger.setLevel(level)
        return level

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
    @Argument("-A", "--arch", nargs=1)
    def arch(self, arch=None):
        """Architecture to build for."""

        # We should be able to make an image for other architectures, but
        # the default should be this machine's.
        if arch is None:
            arch = Architecture(platform.machine())
            logger.info("Assuming CPU architecture '{}'.".format(arch))
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
            logger.info("Assuming image format '{}'.".format(format_))

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
            logger.info(
                "Searching '{}' for vboot keys."
                .format(d)
            )

        # Defaults to distro-specific paths for necessary files.
        keydir, keyblock, signprivate, signpubkey = vboot_keys(*keydirs)

        if self.keyblock is None:
            self.keyblock = keyblock
        if self.signprivate is None:
            self.signprivate = signprivate
        if self.signpubkey is None:
            self.signpubkey = signpubkey

        # We might still not have the vboot keys after all that.
        if self.keyblock is None:
            raise ValueError("Couldn't find a usable keyblock file.")
        else:
            logger.info("Using keyblock file '{}'.".format(self.keyblock))

        if self.signprivate is None:
            raise ValueError("Couldn't find a usable signprivate file.")
        else:
            logger.info("Using signprivate file '{}'.".format(self.signprivate))

        if self.signpubkey is None:
            logger.warn("Couldn't find a usable signpubkey file.")
        else:
            logger.info("Using signpubkey file '{}'.".format(self.signpubkey))


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
            if self.compress == "lz4":
                logger.info("Compressing kernel with lz4.")
                vmlinuz = vmlinuz.lz4()
            elif self.compress == "lzma":
                logger.info("Compressing kernel with lzma.")
                vmlinuz = vmlinuz.lzma()
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
                bootloader = bootloader.copy_to(tmpdir)
            else:
                bootloader = tmpdir / "bootloader.bin"
                bootloader.write_bytes(bytes(512))
                logger.info("Using dummy file for bootloader.")

            if self.image_format == "fit":
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
                    "-A", self.arch.mkimage,
                    "-O", "linux",
                    "-C", self.compress,
                    "-n", self.name,
                    *initramfs_args,
                    *dtb_args,
                    "-d", vmlinuz,
                    fit_image,
                )
                logger.info(proc.stdout)

                logger.info("Using FIT image as vboot kernel.")
                vmlinuz_vboot = fit_image

            elif self.image_format == "zimage":
                logger.info("Using vmlinuz file as vboot kernel.")
                vmlinuz_vboot = vmlinuz

            logger.info("Packing files as depthcharge image.")
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
            logger.info(proc.stdout)

            logger.info("Verifying built depthcharge image:")
            signpubkey_args = []
            if self.signpubkey is not None:
                signpubkey_args += ["--signpubkey", self.signpubkey]

            proc = vbutil_kernel(
                "--verify", self.output,
                *signpubkey_args,
            )
            logger.info(proc.stdout)

        return self.output


if __name__ == "__main__":
    mkdepthcharge.main()
