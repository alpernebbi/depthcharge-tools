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

Right now these are developed on and tested with only one arm64 machine,
so only that is explicitly supported. However, it will probably work
with ARM machines just by adding an entry in the `machine database`_.
Support for `x86 machines`_ is very limited at a fundamental level and
even those parts are untested.

.. _depthcharge: https://chromium.googlesource.com/chromiumos/platform/depthcharge
.. _the format depthcharge expects: https://www.chromium.org/chromium-os/chromiumos-design-docs/disk-format#TOC-Google-Chrome-OS-devices
.. _Debian: https://www.debian.org/


mkdepthcharge
=============
The mkdepthcharge tool is intended to wrap mkimage_ and vbutil_kernel_
to provide reasonable defaults to them, hide their idiosyncrasies and
automate creating a depthcharge-bootable partition image appropriate for
the running architecture. An example invocation on a Samsung Chromebook
Plus (v1, arm64) could be::

    $ mkdepthcharge -o depthcharge.img --compress lzma \
        --cmdline "console=tty1 root=/dev/mmcblk0p2 rootwait" \
        /boot/vmlinuz.gz /boot/initrd.img rk3399-gru-kevin.dtb

Here, mkdepthcharge would automatically extract and recompress the
kernel, create a FIT image, put command line parameters into a file,
create an empty bootloader, and provide defaults for vboot keys and
other arguments while building the partition image.

.. _mkimage: https://dyn.manpages.debian.org/jump?q=unstable/mkimage
.. _vbutil_kernel: https://dyn.manpages.debian.org/jump?q=unstable/vbutil_kernel


depthchargectl
==============
The depthchargectl tool goes a step further and aims to fully automate
bootable image creation and ChromeOS kernel partition management, even
the machine-specific and distro-specific parts. With proper integration
with your distribution, depthchargectl can keep your system bootable
across kernel and initramfs changes without any interaction on your
part. Even without such integration, a single command automates most of
the work::

    # Use --allow-current if you only have one ChromeOS kernel partition.
    $ sudo depthchargectl write --allow-current
    depthchargectl build: Built image for kernel version '5.4.0-1-arm64'.
    depthchargectl write: Wrote image for kernel version '5.4.0-1-arm64' to '/dev/mmcblk1p1'.
    depthchargectl write: Set '/dev/mmcblk1p1' as next to boot.

    # After a reboot, you or an init service should run this.
    $ sudo depthchargectl set-good
    depthchargectl set-good: Set '/dev/mmcblk1p1' as next to boot, successful.


Installation
============
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

After that, you can edit |CONFIG_FILE| to set the kernel command line or
vboot keys to be used.

There is also an optional systemd service to set partitions as
successful on boot::

    $ sudo make install-systemd
    $ systemctl daemon-reload
    $ systemctl --enable depthchargectl-set-good

You can also run the files directly from the repository but you would
need to add the repository to ``$PATH`` first. This is mostly useful
for development::

    # From the root of the repository:
    $ PATH=".:$PATH" ./mkdepthcharge ...
    $ sudo PATH=".:$PATH" ./depthchargectl ...

.. |CONFIG_FILE| replace:: ``/usr/local/etc/depthcharge-tools/config``


Contributing
============
I only own one chromebook, so I need your help to make it work with all
others. Pull requests, bug reports, or even pointers in the right
direction for existing issues are all welcome. The following are the
issues I consider most important for now:

Machine Database
----------------
Different ChromeOS machines have different sets of requirements for
bootable images, so depthchargectl has to track them to build images
that work on a specific machine. These are stored in the |DB_FILE|
file. You can test whether depthchargectl works with your machine by
adding a block to the |USERDB_FILE| file for your machine similar to
those in the main database file.

.. |DB_FILE| replace:: ``/usr/local/share/depthcharge-tools/db``
.. |USERDB_FILE| replace:: ``/usr/local/etc/depthcharge-tools/userdb``

x86 Machines
------------
If you can already get an x86 ChromeOS machine to boot with your
manually built images, you can test if images built by mkdepthcharge
boot successfully as well.

Right now, mkdepthcharge can built images in a 'zimage' format, meaning
it will just pass the kernel executable to vbutil_kernel without an
initramfs. If you know of a way to create x86 boot images that can use
an initramfs, I'd be glad to hear it.


License
=======
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>
