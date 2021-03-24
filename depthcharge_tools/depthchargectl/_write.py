#! /usr/bin/env python3

import argparse
import logging

from depthcharge_tools import (
    __version__,
)
from depthcharge_tools.utils import (
    Path,
    Command,
    Argument,
    Group,
    installed_kernels,
    system_disks,
)


from depthcharge_tools.depthchargectl import depthchargectl

logger = logging.getLogger(__name__)


@depthchargectl.subcommand("write")
class depthchargectl_write(
    depthchargectl,
    prog="depthchargectl write",
    usage="%(prog)s [options] (kernel-image | image)",
    add_help=False,
):
    """Write an image to a ChromeOS kernel partition."""

    config_section = "depthchargectl/write"

    @Group
    def positionals(self):
        """Positional arguments"""

        if self.image is not None and self.kernel_version is not None:
            return ValueError(
                "Image and kernel_version arguments are mutually exclusive"
            )

        image = self.image or self.kernel_version
        kernels = installed_kernels()

        if image is None:
            self.kernel_version = max(kernels)
            self.image = None

        elif isinstance(image, str):
            for k in kernels:
                if image == k.release:
                    logger.info(
                        "Using image for given kernel version '{}'."
                        .format(k.release)
                    )
                    self.kernel_version = k.release
                    self.image = None
                    break
            else:
                self.kernel_version = None
                self.image = Path(image).resolve()
                logger.info("Using given image '{}'.".format(image))

    @positionals.add
    @Argument(dest=argparse.SUPPRESS, nargs=argparse.SUPPRESS)
    def kernel_version(self, kernel_version):
        """Installed kernel version to write to disk."""
        return kernel_version

    @positionals.add
    @Argument
    def image(self, image=None):
        """Depthcharge image to write to disk."""
        return image

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-f", "--force", force=True)
    def force(self, force=False):
        """Write image even if it cannot be verified."""
        return force

    @options.add
    @Argument("-t", "--target", metavar="DISK|PART")
    def target(self, target):
        """Specify a disk or partition to write to."""
        return target

    @options.add
    @Argument("--no-prioritize", prioritize=False)
    def prioritize(self, prioritize=True):
        """Don't set any flags on the partition."""
        return prioritize

    @options.add
    @Argument("--allow-current", allow=True)
    def allow_current(self, allow=False):
        """Allow overwriting the currently booted partition."""
        return allow

    def __call__(self):
        if self.image is not None:
            image = self.image

        else:
            # No image given, try creating one.
            logger.info(
                "Using image for newest installed kernel version '{}'."
                .format(self.kernel_version)
            )
            image = depthchargectl.build(
                kernel_version=self.kernel_version,
            )

        try:
            # This also checks if the machine is supported.
            depthchargectl.check(image=image)
        except Exception as err:
            if force:
                logger.warn(
                    "Depthcharge image '{}' is not bootable on this "
                    "board, continuing due to --force."
                    .format(image)
                )
            else:
                raise ValueError(
                    "Depthcharge image '{}' is not bootable on this "
                    "board."
                    .format(image)
                )

        # We don't want target to unconditionally avoid the current
        # partition since we will also check that here. But whatever we
        # choose must be bigger than the image we'll write to it.
        logger.info("Searching disks for a target partition.")
        try:
            target = depthchargectl.target(
                disks=[self.target] if self.target else (),
                min_size=image.stat().st_size,
                allow_current=self.allow_current,
            )
        except:
            raise ValueError(
                "Couldn't find a usable partition to write to."
            )

        if target.path is None:
            raise ValueError(
                "Cannot write to target partition '{}' without a path."
                .format(target)
            )

        logger.info("Targeted partition '{}'.".format(target))

        # Check and warn if we targeted the currently booted partition,
        # as that usually means it's the only partition.
        current = system_disks.by_kern_guid()
        if self.allow_current and target.path == current.path:
            logger.warn(
                "Overwriting the currently booted partition '{}'. "
                "This might make your system unbootable."
                .format(target)
            )

        logger.info(
            "Writing depthcharge image '{}' to partition '{}'."
            .format(image, target)
        )
        target.path.write_bytes(image.read_bytes())
        logger.info(
            "Wrote depthcharge image '{}' to partition '{}'."
            .format(image, target)
        )

        if self.prioritize:
            logger.info(
                "Setting '{}' as the highest-priority bootable part."
                .format(target)
            )
            target.attribute = 0x010
            target.prioritize()
            logger.info(
                "Set partition '{}' as next to boot."
                .format(target)
            )

    global_options = depthchargectl.global_options
    config_options = depthchargectl.config_options

