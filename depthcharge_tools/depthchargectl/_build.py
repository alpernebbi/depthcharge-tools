#! /usr/bin/env python3

import argparse
import collections
import configparser
import logging
import os
import shlex
import textwrap

from pathlib import Path
from functools import lru_cache

from depthcharge_tools import __version__
from depthcharge_tools.mkdepthcharge import mkdepthcharge
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
    CommandExit,
)
from depthcharge_tools.utils.os import (
    system_disks,
    Disks,
    Partition,
)
from depthcharge_tools.utils.pathlib import (
    copy,
)
from depthcharge_tools.utils.platform import (
    KernelEntry,
    installed_kernels,
    root_requires_initramfs,
)
from depthcharge_tools.utils.subprocess import (
    fdtget,
)

from depthcharge_tools.depthchargectl import depthchargectl


class SizeTooBigError(CommandExit):
    def __init__(self):
        super().__init__(
            "Couldn't build a small enough image for this board.",
            returncode=4,
        )


class InitramfsSizeTooBigError(SizeTooBigError):
    def __init__(self):
        super(SizeTooBigError, self).__init__(
            "Couldn't build a small enough image for this board. "
            "This is usually solvable by making the initramfs smaller, "
            "check your OS's documentation on how to do so.",
            returncode=3,
        )


@depthchargectl.subcommand("build")
class depthchargectl_build(
    depthchargectl,
    prog="depthchargectl build",
    usage="%(prog)s [options] [KERNEL_VERSION]",
    add_help=False,
):
    """Buld a depthcharge image for the running system."""

    logger = depthchargectl.logger.getChild("build")
    config_section = "depthchargectl/build"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__chroot = None

    @Group
    def positionals(self):
        """Positional arguments"""

    @positionals.add
    @Argument
    def kernel_version(self, kernel_version=None):
        """Installed kernel version to build an image for."""
        if isinstance(kernel_version, KernelEntry):
            return kernel_version

        kernels = installed_kernels(
            root=self.root_mountpoint,
            boot=self.boot_mountpoint,
        )

        if isinstance(kernel_version, str):
            kernel = max(
                (k for k in kernels if k.release == kernel_version),
                default=None,
            )

            if kernel is None:
                raise ValueError(
                    "Could not find an installed kernel for version '{}'."
                    .format(kernel_version)
                )

        elif kernels:
            kernel = max(kernels)

        else:
            self.logger.warning(
                "Could not find any installed kernel."
            )
            kernel = None

        return kernel

    @Group
    def options(self):
        """Options"""

    @depthchargectl.board.copy()
    def board(self, codename=""):
        board = super().board

        if board is None:
            raise ValueError(
                "Cannot build depthcharge images when no board is specified.",
            )

        return board

    @Group
    def custom_kernel_options(self):
        """Custom kernel specification"""

    @custom_kernel_options.add
    @Argument("--kernel-release", nargs=1)
    def kernel_release(self, name=None):
        """Release name for the kernel used in image name"""
        if name is None and self.kernel_version is not None:
            if self.kernel == self.kernel_version.kernel:
                name = self.kernel_version.release

        return name

    @custom_kernel_options.add
    @Argument("--kernel", nargs=1)
    def kernel(self, file_=None):
        """Kernel executable"""
        if file_ is None and self.kernel_version is not None:
            file_ = self.kernel_version.kernel

        # vmlinuz is always mandatory
        if file_ is None:
            raise ValueError(
                "No vmlinuz file found for version '{}'."
                .format(self.kernel_release or "(unknown)")
            )

        return Path(file_)

    @custom_kernel_options.add
    @Argument("--initramfs", nargs=1)
    def initrd(self, file_=None):
        """Ramdisk image"""
        if file_ is None and self.kernel_version is not None:
            if self.kernel == self.kernel_version.kernel:
                file_ = self.kernel_version.initrd

        if self.ignore_initramfs:
            self.logger.warning(
                "Ignoring initramfs '{}' as configured."
                .format(file_)
            )
            return None

        # Initramfs is optional.
        if file_ is None:
            self.logger.info(
                "No initramfs file found for version '{}'."
                .format(self.kernel_release or "(unknown)")
            )
            return None

        else:
            return Path(file_)

    @custom_kernel_options.add
    @Argument("--fdtdir", nargs=1)
    def fdtdir(self, dir_=None):
        """Directory to search device-tree binaries for the board"""
        if dir_ is None and self.kernel_version is not None:
            if self.kernel == self.kernel_version.kernel:
                dir_ = self.kernel_version.fdtdir

        if dir_ is None:
            return None
        else:
            return Path(dir_)

    @custom_kernel_options.add
    @Argument("--dtbs", nargs="+", metavar="FILE")
    def dtbs(self, *files):
        """Device-tree binary files to use instead of searching fdtdir"""

        # Device trees are optional based on board configuration.
        if self.board.dt_compatible and len(files) == 0:
            if self.fdtdir is None:
                raise ValueError(
                    "No dtb directory found for version '{}', "
                    "but this board needs a dtb."
                    .format(self.kernel_release or "(unknown)")
                )

            self.logger.info(
                "Searching '{}' for dtbs compatible with pattern '{}'."
                .format(self.fdtdir, self.board.dt_compatible.pattern)
            )

            def is_compatible(dt_file):
                return any(
                    self.board.dt_compatible.fullmatch(compat)
                    for compat in fdtget.get(
                        dt_file, "/", "compatible", default="",
                    ).split()
                )

            files = list(filter(
                is_compatible,
                self.fdtdir.glob("**/*.dtb"),
            ))

            if len(files) == 0:
                raise ValueError(
                    "No dtb file compatible with pattern '{}' found in '{}'."
                    .format(self.board.dt_compatible.pattern, self.fdtdir)
                )

        else:
            files = [Path(f) for f in files]

        if self.board.image_format == "zimage" and len(files) != 0:
            raise ValueError(
                "Image format '{}' doesn't support dtb files."
                .format(self.board.image_format)
            )

        return files

    @options.add
    @Argument("--description", nargs=1)
    def description(self, desc=None):
        """Human-readable description for the image"""
        if desc is None and self.kernel_version is not None:
            if self.board.image_format != "zimage":
                desc = self.kernel_version.description

        return desc

    @options.add
    @Argument("--root", nargs=1)
    def root(self, root=None):
        """Root device or mountpoint of the system to build for"""
        if root is None:
            cmdline = self.kernel_cmdline

            for c in cmdline:
                lhs, _, rhs = c.partition("=")
                if lhs.lower() == "root":
                    root = rhs

            if root:
                self.logger.info(
                    "Defaulting to root '{}' set in user configured cmdline."
                    .format(root)
                )

        def get_root_str(*mounts):
            rootset = set()

            for mnt in mounts:
                disks = Disks(
                    fstab=(mnt / "etc" / "fstab"),
                    crypttab=(mnt / "etc" / "crypttab"),
                )
                rootstr = disks.by_mountpoint("/", fstab_only=True)
                if rootstr:
                    rootset.add(rootstr)

            if len(rootset) > 1:
                raise ValueError(
                    "Conflicting root specs {} in multiple /etc/fstab files: {}"
                    .format(roots, [mnt / "etc" / "fstab" for mnt in mounts])
                )

            elif rootset:
                rootstr = rootset.pop()
                self.logger.info(
                    "Using root '{}' as set in /etc/fstab."
                    .format(rootstr)
                )
                return rootstr

            elif Path("/").resolve() in mounts:
                rootstr = system_disks.by_mountpoint("/")
                self.logger.warning(
                    "Couldn't figure out a root cmdline parameter from /etc/fstab."
                    "Will use currently mounted '{}'."
                    .format(rootstr)
                )
                return rootstr

            self.logger.warning(
                "Couldn't figure out a root cmdline parameter for '{}'. "
                "Using as-is."
                .format(root)
            )
            return root

        if root is None:
            self.logger.info(
                "Defaulting to current system root '/'."
                .format(root)
            )
            root_dev = system_disks.by_mountpoint("/")
            root_mnt = {Path("/").resolve()}
            root_str = get_root_str(*root_mnt)

        elif root in ("", "None", "none"):
            self.logger.warning(
                "Will not set a root cmdline parameter."
            )
            root_dev = system_disks.by_mountpoint("/")
            root_mnt = {Path("/").resolve()}
            root_str = None

        elif os.path.ismount(Path(root).resolve()):
            self.logger.info(
                "Using root '{}' as the system to build for."
                .format(root)
            )
            root_dev = system_disks.by_mountpoint(root)
            root_mnt = {Path(root).resolve()}
            root_str = get_root_str(*root_mnt)

        elif system_disks.evaluate(root):
            self.logger.info(
                "Using root '{}' as a device description."
                .format(root)
            )
            root_dev = system_disks.evaluate(root)
            root_mnt = system_disks.mountpoints(root)
            root_str = get_root_str(*root_mnt)

        else:
            self.logger.warning(
                "Using root '{}' but it's not a device or mountpoint."
                .format(root)
            )
            root_dev = system_disks.by_mountpoint("/")
            root_mnt = {Path("/").resolve()}
            root_str = str(root)

        return {
            "device": root_dev,
            "mountpoints": root_mnt,
            "cmdline": root_str,
        }

    @options.add
    @Argument("--root-mountpoint", nargs=1, help=argparse.SUPPRESS)
    def root_mountpoint(self, root=None):
        """Root mountpoint of the system to build for."""
        if root:
            root = Path(root).resolve()
            self.logger.info(
                "Using root mountpoint '{}' from given argument."
                .format(root)
            )
            return root

        mountpoints = sorted(
            self.root["mountpoints"],
            key=lambda p: len(p.parents),
        )

        if len(mountpoints) > 1:
            self.logger.warning(
                "Choosing '{}' from multiple root mountpoints: {}."
                .format(mountpoints[0], mountpoints)
            )

        if mountpoints:
            return mountpoints[0]

        self.logger.warning(
            "Couldn't find root mountpoint, falling back to '/'."
        )

        return Path("/").resolve()

    @options.add
    @Argument("--boot-mountpoint", nargs=1, help=argparse.SUPPRESS)
    def boot_mountpoint(self, boot=None):
        """Boot mountpoint of the system to build for."""
        if boot:
            boot = Path(boot).resolve()
            self.logger.info(
                "Using boot mountpoint '{}' from given argument."
                .format(root)
            )
            return boot

        root = self.root_mountpoint
        disks = Disks(
            fstab=(root / "etc" / "fstab"),
            crypttab=(root / "etc" / "crypttab"),
        )
        boot_str = disks.by_mountpoint("/boot", fstab_only=True)
        device = system_disks.evaluate(boot_str)
        mountpoints = sorted(
            disks.mountpoints(device),
            key=lambda p: len(p.parents),
        )

        if len(mountpoints) > 1:
            self.logger.warning(
                "Choosing '{}' from multiple /boot mountpoints: {}."
                .format(mountpoints[0], mountpoints)
            )

        if mountpoints:
            return mountpoints[0]

        boot = (root / "boot").resolve()
        if boot.is_dir():
            self.logger.info(
                "Couldn't find /boot mountpoint, falling back to '{}'."
                .format(boot)
            )
            return boot

        self.logger.warning(
            "Couldn't find /boot mountpoint, falling back to /boot."
            .format(boot)
        )

        return Path("/boot").resolve()

    @options.add
    @Argument("--root-cmdline", nargs=1, help=argparse.SUPPRESS)
    def root_cmdline(self, root=None):
        """Root parameter to add to kernel cmdline"""
        if root:
            root = str(root)
            if root.startswith("root="):
                root = root[5:]
            return root

        return self.root["cmdline"]

    @depthchargectl.kernel_cmdline.copy()
    def kernel_cmdline(self, *cmds):
        # This is some deep magic that evaluates self.kernel_cmdline
        # according to the parent definition and sets it in self.
        cmdline = super().kernel_cmdline

        # This evaluates self.root with the above self.kernel_cmdline,
        # then continues here to set self.kernel_cmdline a second time.
        append_root = self.root_cmdline is not None

        for c in list(cmdline):
            lhs, _, rhs = c.partition("=")
            if lhs.lower() != "root":
                continue

            if rhs == self.root_cmdline:
                append_root = False
                continue

            self.logger.warning(
                "Kernel cmdline has a different root '{}', removing it."
                .format(rhs)
            )
            cmdline.remove(c)

        if append_root:
            self.logger.info(
                "Appending 'root={}' to kernel cmdline."
                .format(self.root_cmdline)
            )
            cmdline.append('root={}'.format(self.root_cmdline))

        if self.ignore_initramfs:
            self.logger.warning(
                "Ignoring initramfs as configured, "
                "appending 'noinitrd' to the kernel cmdline."
                .format(self.initrd)
            )
            cmdline.append("noinitrd")

        # Linux kernel without an initramfs only supports certain
        # types of root parameters, check for them.
        if self.initrd is None and self.root_cmdline is not None:
            if root_requires_initramfs(self.root_cmdline):
                raise ValueError(
                    "An initramfs is required for root '{}'."
                    .format(self.root_cmdline)
                )

        return cmdline

    @options.add
    @Argument("--compress", nargs="+", metavar="TYPE")
    def compress(self, *compress):
        """Compression types to attempt."""

        # Allowed compression levels. We will call mkdepthcharge by
        # hand multiple times for these.
        for c in compress:
            if c not in ("none", "lz4", "lzma"):
                raise ValueError(
                    "Unsupported compression type '{}'."
                    .format(t)
                )

        if len(compress) == 0:
            compress = ["none"]
            if self.board.boots_lz4_kernel:
                compress += ["lz4"]
            if self.board.boots_lzma_kernel:
                compress += ["lzma"]

            # zimage doesn't support compression
            if self.board.image_format == "zimage":
                compress = ["none"]

        return sorted(set(compress), key=compress.index)

    @options.add
    @Argument("--timestamp", nargs=1)
    def timestamp(self, seconds=None):
        """Build timestamp for the image"""
        if seconds is None:
            if "SOURCE_DATE_EPOCH" in os.environ:
                seconds = os.environ["SOURCE_DATE_EPOCH"]

        # Initramfs date is bound to be later than vmlinuz date, so
        # prefer that if possible.
        if seconds is None:
            if self.initrd is not None:
                seconds = int(self.initrd.stat().st_mtime)
            else:
                seconds = int(self.kernel.stat().st_mtime)

        if seconds is None:
            self.logger.error(
                "Couldn't determine a timestamp from initramfs "
                "nor vmlinuz."
            )

        return seconds

    @options.add
    @Argument("-o", "--output", nargs=1)
    def output(self, path=None):
        """Output image to path instead of storing in images-dir"""
        if path is None:
            image_name = "{}.img".format(self.kernel_release or "default")
            path = self.images_dir / image_name

        return Path(path)

    @depthchargectl.config.copy()
    def config(self, file_=None):
        """Additional configuration file to read"""
        config = super().config
        root = self.root_mountpoint
        boot = self.boot_mountpoint

        if root == Path("/").resolve():
            return config

        parser = configparser.ConfigParser()

        config_files = [
            *root.glob("etc/depthcharge-tools/config"),
            *root.glob("etc/depthcharge-tools/config.d/*"),
        ]

        try:
            for p in parser.read(config_files):
                self.logger.debug("Read config file '{}'.".format(p))

        except configparser.ParsingError as err:
            self.logger.warning(
                "Config file '{}' could not be parsed."
                .format(err.filename)
            )

        file_configs = [
            "images-dir",
            "vboot-keyblock",
            "vboot-public-key",
            "vboot-private-key",
        ]

        def fixup_path(f):
            p = Path(f).resolve()
            if f.startswith("/boot"):
                return str(boot / p.relative_to("/boot"))
            elif f.startswith("/"):
                return str(root / p.relative_to("/"))

        for sect, conf in parser.items():
            for key, value in conf.items():
                if key in file_configs:
                    conf[key] = fixup_path(value)

        # Re-override with values from custom config file argument
        if isinstance(file_, collections.abc.Mapping):
            parser[self.config_section].update(file_)

        elif file_ is not None:
            try:
                read = parser.read([file_])

            except configparser.ParsingError as err:
                raise ValueError(
                    "Config file '{}' could not be parsed."
                    .format(err.filename)
                )

            if file_ not in read:
                raise ValueError(
                    "Config file '{}' could not be read."
                    .format(file_)
                )

        # Merge into actual config
        config.parser.read_dict(parser)

        return config

    def __call__(self):
        self.logger.warning(
            "Building depthcharge image for board '{}' ('{}')."
            .format(self.board.name, self.board.codename)
        )

        self.logger.info(
            "Building for kernel version '{}'."
            .format(self.kernel_release or "(unknown)")
        )

        # Images dir might not have been created at install-time
        os.makedirs(self.output.parent, exist_ok=True)

        # Build to a temporary file so we do not overwrite existing
        # images with an unbootable image.
        outtmp = self.tmpdir / "{}.tmp".format(self.output.name)

        # Try to keep output reproducible.
        if self.timestamp is not None:
            os.environ["SOURCE_DATE_EPOCH"] = str(self.timestamp)

        # Error early if initramfs is absolutely too big to fit
        initrd_size = (
            self.initrd.stat().st_size
            if self.initrd is not None
            else 0
        )
        if initrd_size >= self.board.image_max_size:
            self.logger.error(
                "Initramfs alone is larger than the maximum image size."
            )
            raise InitramfsSizeTooBigError()

        # Skip compress="none" if inputs wouldn't fit max image size
        compress_list = self.compress
        inputs_size = sum([
            self.kernel.stat().st_size,
            initrd_size,
            *(dtb.stat().st_size for dtb in self.dtbs),
        ])

        if inputs_size > self.board.image_max_size and "none" in compress_list:
            self.logger.info(
                "Inputs are too big, skipping uncompressed build."
            )
            compress_list.remove("none")

        for compress in compress_list:
            self.logger.info("Trying with compression '{}'.".format(compress))
            tmpdir = self.tmpdir / "mkdepthcharge-{}".format(compress)

            try:
                mkdepthcharge(
                    arch=self.board.arch,
                    cmdline=self.kernel_cmdline,
                    compress=compress,
                    dtbs=self.dtbs,
                    image_format=self.board.image_format,
                    initramfs=self.initrd,
                    keyblock=self.vboot_keyblock,
                    name=self.description,
                    output=outtmp,
                    signprivate=self.vboot_private_key,
                    signpubkey=self.vboot_public_key,
                    vmlinuz=self.kernel,
                    tmpdir=tmpdir,
                    verbosity=self.verbosity,
                )

            except Exception as err:
                raise CommandExit(
                    "Failed while creating depthcharge image.",
                ) from err

            if outtmp.stat().st_size < self.board.image_max_size:
                break

            self.logger.warning(
                "Image with compression '{}' is too big for this board."
                .format(compress)
            )

        else:
            if self.initrd is not None:
                raise InitramfsSizeTooBigError()
            else:
                raise SizeTooBigError()

        self.logger.info("Copying newly built image to output.")
        copy(outtmp, self.output)

        self.logger.warning(
            "Built depthcharge image for kernel version '{}'."
            .format(self.kernel_release or "(unknown)")
        )
        return self.output

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options

