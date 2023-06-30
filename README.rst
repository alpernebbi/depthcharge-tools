.. SPDX-License-Identifier: GPL-2.0-or-later

.. depthcharge-tools README file
.. Copyright (C) 2019-2023 Alper Nebi Yasak <alpernebiyasak@gmail.com>
.. See COPYRIGHT and LICENSE files for full copyright information.

=================
Depthcharge-Tools
=================
This project is a collection of tools that ease and automate interacting
with depthcharge_, the Chrome OS bootloader.

Depthcharge is built into the firmware of Chrome OS boards, uses a
custom verified boot flow and usually cannot boot other operating
systems as is. This means someone who wants to use e.g. Debian_ on these
boards need to either replace the firmware or work their system into
`the format depthcharge expects`_. These tools are about the latter.

Right now these are developed on and tested with only a few boards,
but everything will attempt to work on other boards based on my best
guesses.

.. _depthcharge: https://chromium.googlesource.com/chromiumos/platform/depthcharge
.. _the format depthcharge expects: https://chromium.googlesource.com/chromiumos/docs/+/HEAD/disk_format.md#Google-ChromeOS-devices
.. _Debian: https://www.debian.org/


mkdepthcharge
=============
The mkdepthcharge_ tool is intended to wrap mkimage_ and vbutil_kernel_
to provide reasonable defaults to them, hide their idiosyncrasies and
automate creating a depthcharge-bootable partition image appropriate for
the running architecture. An example invocation on a Samsung Chromebook
Plus (v1, arm64) could be::

    $ mkdepthcharge -o depthcharge.img --compress lzma \
        --cmdline "console=tty1 root=/dev/mmcblk0p2 rootwait" -- \
        /boot/vmlinuz.gz /boot/initrd.img rk3399-gru-kevin.dtb

Here, mkdepthcharge would automatically extract and recompress the
kernel, create a FIT image, put command line parameters into a file,
create an empty bootloader, and provide defaults for vboot keys and
other arguments while building the partition image.

.. _mkdepthcharge: https://github.com/alpernebbi/depthcharge-tools/blob/master/mkdepthcharge.rst
.. _mkimage: https://dyn.manpages.debian.org/jump?q=unstable/mkimage
.. _vbutil_kernel: https://dyn.manpages.debian.org/jump?q=unstable/vbutil_kernel


depthchargectl
==============
The depthchargectl_ tool goes a step further and aims to fully automate
bootable image creation and Chrome OS kernel partition management, even
the board-specific and distro-specific parts. With proper integration
with your distribution, depthchargectl can keep your system bootable
across kernel and initramfs changes without any interaction on your
part. Even without such integration, a single command automates most of
the work::

    # Use --allow-current if you only have one Chrome OS kernel partition.
    $ sudo depthchargectl write --allow-current
    Building depthcharge image for board 'Samsung Chromebook Plus' ('kevin').
    Built depthcharge image for kernel version '5.10.0-6-arm64'.
    Wrote image '/boot/depthcharge/5.10.0-6-arm64.img' to partition '/dev/mmcblk1p1'.
    Set partition '/dev/mmcblk1p1' as next to boot.

    # After a reboot, you or an init service should run this.
    $ sudo depthchargectl bless
    Set partition '/dev/mmcblk1p1' as successfully booted.

.. _depthchargectl: https://github.com/alpernebbi/depthcharge-tools/blob/master/depthchargectl.rst


Installation
============
This depends on the ``pkg_resources`` Python package which is usually
distributed with ``setuptools``. The tools can run a number of programs
when necessary, which should be considered dependencies:

- ``futility`` (``vbutil_kernel``), ``cgpt``, ``crossystem``
- ``mkimage``, ``fdtget``, ``fdtput``
- ``lz4``, ``lzma``
- ``gzip``, ``lzop``, ``bzip2``, ``xz``, ``zstd``
  (optional, for unpacking compressed ``/boot/vmlinuz``)

The ``rst2man`` program (from ``docutils``) should be used to convert
the ``mkdepthcharge.rst`` and ``depthchargectl.rst`` files to manual
pages. However, this is not automated here and has to be done manually.

This project (or at least ``depthchargectl``) is meant to be integrated
into your operating system by its maintainers, and the best way to
install it is through your OS' package manager whenever possible.


Debian
------
An official `depthcharge-tools Debian package`_ is available upstream,
since Debian 12 (bookworm). You can install it like any other package::

    $ sudo apt install depthcharge-tools

It includes the necessary system hooks and services to make and keep
your Chromebook bootable, enabled by default. These however do not
trigger on the depthcharge-tools installation, but on kernel and
initramfs changes. To trigger these hooks manually, run::

    $ sudo update-initramfs -u

.. _depthcharge-tools Debian package: https://packages.debian.org/sid/depthcharge-tools


Alpine Linux
------------
Thanks to the efforts in supporting `postmarketOS on ChromeOS Devices`_,
there is an official `depthcharge-tools package for Alpine Linux`_. You
should be able to install it as::

    $ sudo apk add depthcharge-tools

However, this doesn't include any system hooks or services to keep your
Chromebook bootable.

.. _postmarketOS on ChromeOS Devices: https://wiki.postmarketos.org/wiki/Chrome_OS_devices
.. _depthcharge-tools package for Alpine Linux: https://pkgs.alpinelinux.org/package/edge/testing/x86/depthcharge-tools


Pip
---
Python binary wheels are uploaded to PyPI_, and it should be possible to
install the python package using `pip`. However, this does not install
the manual pages, bash/zsh completions, systemd/init.d service files,
and OS-specific kernel/initramfs hooks.

You can install in `--user` mode, but this makes it quite hard to use
`depthchargectl` as root. As root privileges are necessary to manipulate
system block devices this limits you a bit::

    $ pip install --user depthcharge-tools

Although inadvisable, you can install as root to overcome that caveat.
Alternatively, see the `PYTHONPATH` hack in one of the later sections.

.. _PyPI: https://pypi.org/project/depthcharge-tools/


Configuration
=============
You can configure depthcharge-tools with the |CONFIG_FILE| file, or by
putting similar fragments in the |CONFIGD_DIR| directory. See the
config.ini_ file for the built-in default configuration.

Settings in the ``[depthcharge-tools]`` section are the global defaults
from which all commands inherit. Other than that, config sections have
inheritence based on their names i.e. those in the form of ``[a/b/c]``
inherit from ``[a/b]`` which also inherits from ``[a]``. Each subcommand
reads its config from such a subsection.

Currently the following configuration options are available::

    [depthcharge-tools]
    enable-system-hooks: Write/remove images on kernel/initramfs changes
    vboot-keyblock: The kernel keyblock file for verifying and signing images
    vboot-private-key: The private key (.vbprivk) for signing images
    vboot-public-key: The public key for (.vbpubk) verifying images

    [depthchargectl]
    board: Codename of a board to build and check images for
    ignore-initramfs: Do not include an initramfs in the image
    images-dir: Directory to store built images
    kernel-cmdline: Kernel commandline parameters to use
    zimage-initramfs-hack = How to support initramfs on x86 boards

For longer explanations check the manual pages of each command for
options named the same as these.

.. |CONFIG_FILE| replace:: ``/etc/depthcharge-tools/config``
.. |CONFIGD_DIR| replace:: ``/etc/depthcharge-tools/config.d``
.. _config.ini: https://github.com/alpernebbi/depthcharge-tools/blob/master/depthcharge_tools/config.ini


Installation for development
============================
If you want to use development versions, you can clone this repository
and install using pip::

    $ pip3 install --user -e /path/to/depthcharge-tools

Hopefully, you should be able to use depthchargectl with just that::

    $ depthchargectl build --output depthcharge.img
    Building depthcharge image for board 'Samsung Chromebook Plus' ('kevin').
    Built depthcharge image for kernel version '5.10.0-6-arm64'.
    depthchargectl.img

Most ``depthchargectl`` functionality needs root as it handles disks and
partitions, and you need special care while invoking as root::

    $ depthchargectl() {
        sudo PYTHONPATH=/path/to/depthcharge-tools \
            python3 -m depthcharge_tools.depthchargectl "$@"
    }

    $ depthchargectl list /dev/mmcblk0
    S  P  T  PATH
    1  2  0  /dev/mmcblk0p2
    1  1  0  /dev/mmcblk0p4
    0  0  15 /dev/mmcblk0p6

Or you can add a similar invocation to the /usr/local/bin files, so that
it's available to both normal users and root::

    $ sudo tee /usr/local/bin/depthchargectl <<EOF
    #!/bin/sh
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONPATH=/path/to/depthcharge-tools
    exec python3 -m depthcharge_tools.depthchargectl "\$@"
    EOF

    $ sudo chmod +x /usr/local/bin/depthchargectl


License
=======
Copyright (C) 2019-2023 Alper Nebi Yasak <alpernebiyasak@gmail.com>

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

See COPYRIGHT and LICENSE files for full copyright information.
