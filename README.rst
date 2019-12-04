=================
Depthcharge-Tools
=================
This project is a collection of tools that ease and automate interacting
with depthcharge_, the ChromeOS bootloader.

Depthcharge is built into the firmware of ChromeOS machines, uses a
custom verified boot flow and usually cannot boot other operating
systems as is. This means someone who wants to use e.g. Debian_ on these
machines need to either replace the firmware or work their system into
`the format depthcharge expects`_. These tools are about the latter.

.. _depthcharge: https://chromium.googlesource.com/chromiumos/platform/depthcharge
.. _the format depthcharge expects: https://www.chromium.org/chromium-os/chromiumos-design-docs/disk-format#TOC-Google-Chrome-OS-devices
.. _Debian: https://www.debian.org/

mkdepthcharge
-------------
The mkdepthcharge tool is intended to wrap mkimage_ and vbutil_kernel_
to provide reasonable defaults to them and create a depthcharge-bootable
partition image appropriate for the running architecture. An example
invocation on the Samsung Chromebook Plus (v1, arm64) could be::

    $ mkdepthcharge -o depthcharge.img --compress lzma \
        --cmdline "console=tty1 root=/dev/mmcblk0p2 rootwait" \
        /boot/vmlinuz.gz /boot/initrd.img rk3399-gru-kevin.dtb

Here, mkdepthcharge automates some stuff for us:

- Decompresses the gzip-packaged kernel file.
- Defaults to creating a FIT image since it's an arm/arm64 system.
- Recompresses the kernel with lzma since we're building a FIT image.
- Sets common unchanging arguments to mkimage and vbutil_kernel.
- Adds ``kern_guid=%U`` to cmdline to know which partition we booted from.
- Writes the cmdline paramters to a file as vbutil_kernel expects.
- Uses a dummy 'bootloader' (on arm/arm64) as vbutil_kernel requires one.
- Uses the vbutil_kernel key paths provided at installation time.

.. _mkimage: https://dyn.manpages.debian.org/jump?q=unstable/mkimage
.. _vbutil_kernel: https://dyn.manpages.debian.org/jump?q=unstable/vbutil_kernel

depthchargectl
--------------
The depthchargectl tool goes a step further and aims to fully automate
bootable image creation and ChromeOS kernel partition management, even
the machine-specific and distro-specific parts. With proper integration
with your distribution, depthchargectl can keep your system bootable
across kernel and initramfs changes without any interaction on your
part.

depthchargectl check
~~~~~~~~~~~~~~~~~~~~
The check subcommand can verify that an image is bootable on your
machine by keeping track of known ChromeOS machines with their
requirements and restrictions.

depthchargectl build
~~~~~~~~~~~~~~~~~~~~
The build subcommand can automatically build an image from the running system
that will work on your device:

- Chooses the most recent vmlinuz and initramfs files for your distro.
- Chooses the correct device-tree blob for your machine, if any.
- Uses an appropriate root command-line parameter derived from /etc/fstab.
- Tries better compression values as needed, if your firmware allows it.
- Raises an error if it can't build a bootable image e.g. when it's too big.
- Handles storage and caching of built images.

depthchargectl write
~~~~~~~~~~~~~~~~~~~~
The write subcommand can automatically write a depthcharge-bootable
image to disk. By default, it will build, check and write an image for
your system to where the target subcommand sees fit and mark it as
the preferred (but not yet successful) partition on the next boot.

When you have more than one ChromeOS kernel partition, they will be
utilized in rotation so that an unsuccessful boot can revert to the
last good version.

depthchargectl partitions
~~~~~~~~~~~~~~~~~~~~~~~~~
The partitions subcommand provides a table of ChromeOS kernel partitions
and their flags. By default it will show those on the boot-time physical
disks for your system (those where /boot and root are located).

depthchargectl target
~~~~~~~~~~~~~~~~~~~~~
The target subcommand chooses an appropriate ChromeOS kernel partition
to write a boot image to. It tries to avoid choosing the currently
booted partition.

depthchargectl set-good
~~~~~~~~~~~~~~~~~~~~~~~
The set-good subcommand modifies the flags on the currently booted
partition so that it's the highest priority successful partition. The
write subcommand marks partitions as bootable only once, and the
set-good subcommand must be run to make them permanently bootable.

depthchargectl rm
~~~~~~~~~~~~~~~~~
The rm subcommand disables partitions that contain a specific image.
This is most useful when you are removing a kernel version (and its
modules) from your machine and know images built with that kernel will
fail to boot from that point on.
