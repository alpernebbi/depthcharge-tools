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

Installation
------------
These tools depend on ``mkimage``, ``vbutil_kernel``, ``cgpt``, and other
utilities (``util-linux``, ``coreutils``, etc.) that are usually
installed by default on most Linux systems.

To install depthcharge-tools to ``/usr/local/``, run::

    $ make
    $ sudo make install

Hopefully, you should be able to use depthchargectl with just that::

    $ sudo depthchargectl partitions /dev/mmcblk0
    S  P  T  DEVICE
    1  2  0  /dev/mmcblk0p2
    1  1  0  /dev/mmcblk0p4
    0  0  15 /dev/mmcblk0p6

After that, you can edit ``/usr/local/etc/depthcharge-tools/config`` to
set the kernel command line or vboot keys to be used.

There is also an optional systemd service to set partitions as
successful on boot::

    $ sudo make install-systemd
    $ systemctl daemon-reload
    $ systemctl --enable depthchargectl-set-good
