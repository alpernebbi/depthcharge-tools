=============
mkdepthcharge
=============

---------------------------------------------
Build boot images for the ChromeOS bootloader
---------------------------------------------

:date: 2021-04-27
:version: v0.5.0
:manual_section: 1
:manual_group: depthcharge-tools

.. |mkimage| replace:: *mkimage*\ (1)
.. |vbutil_kernel| replace:: *vbutil_kernel*\ (1)
.. |futility| replace:: *futility*\ (1)

.. |VBOOT_DEVKEYS| replace:: /usr/share/vboot/devkeys
.. |VBOOT_KEYBLOCK| replace:: |VBOOT_DEVKEYS|/kernel.keyblock
.. |VBOOT_SIGNPUBKEY| replace:: |VBOOT_DEVKEYS|/kernel_subkey.vbpubk
.. |VBOOT_SIGNPRIVATE| replace:: |VBOOT_DEVKEYS|/kernel_data_key.vbprivk

SYNOPSIS
========
**mkdepthcharge** **-o** *FILE* [options] [*VMLINUZ*] [*INITRAMFS*] [*DTB* ...]


DESCRIPTION
===========
**mkdepthcharge** wraps the |mkimage| and |vbutil_kernel|
programs with reasonable defaults to package its inputs into the
format the ChromeOS bootloader expects. It also automates many actions
that a user would have to do manually or write a script for.

The *VMLINUZ* should be a kernel executable, *INITRAMFS* should be a
ramdisk image that the kernel should be able to use on its own, and
*DTB* files should be device-tree binary files appropriate for the
kernel.

**mkdepthcharge** tries to determine the type of each input file by some
heuristics on their contents, but failing that it assumes a file is
whatever is missing in the *VMLINUZ*, *INITRAMFS*, *DTB* order.
Alternatively, these files can be specified as options instead of
positional arguments.


OPTIONS
=======

Input files
-----------

-d VMLINUZ, --vmlinuz VMLINUZ
    Kernel executable.  If a gzip-compressed file is given here, it is
    decompressed and its contents are used in its place.

-i INITRAMFS, --initramfs INITRAMFS
    Ramdisk image

-b *DTB* [*DTB* ...], --dtbs *DTB* [*DTB* ...]
    Device-tree binary files

Global options
--------------
-A ARCH, --arch ARCH
    Architecture to build the images for.  The following architectures
    are understood: **arm**, **arm64**, **aarch64** for ARM machines;
    **x86**, **x86_64**, **amd64** for x86 machines. If not given, the
    output of **uname -m** is used.

--format FORMAT
    Kernel image format to use, either **fit** or **zimage**. If not
    given, architecture-specific defaults are used.

    fit
        This is the default on ARM machines. The *VMLINUZ* and the
        optional *INITRAMFS*, *DTB* files are packaged into the
        Flattened Image Tree (FIT) format using |mkimage| and that is
        passed to |vbutil_kernel|.

    zimage
        This is the default for x86 machines. The *VMLINUZ* is passed
        unmodified (except decompression) to |vbutil_kernel|. It does
        not support packaging *INITRAMFS* or *DTB* files.

-h, --help
    Show a help message and exit.

-o FILE, --output FILE
    Write the image to *FILE*. The image isn't generated at the output,
    but copied to it from a temporary working directory. This option is
    mandatory.

-v, --verbose
    Print info messages, |mkimage| output and |vbutil_kernel| output to
    stderr.

-V, --version
    Print program version and exit.

FIT image options
-----------------
-C TYPE, --compress TYPE
    Compress the *VMLINUZ* before packaging it into a FIT image, either
    with **lz4** or **lzma**. **none** is also accepted, but does
    nothing.

-n DESC, --name DESC
    Description of the *VMLINUZ* to put in the FIT image.

Depthcharge image options
-------------------------
--bootloader FILE
    Bootloader stub. If not given, an empty file is used.

-c *CMD* [*CMD* ...], --cmdline *CMD* [*CMD* ...]
    Command-line parameters for the kernel. Can be used multiple times
    to append new values. If not given, **--** is used.

    The ChromeOS bootloader expands any instance of **%U** in the kernel
    command line with the PARTUUID of the ChromeOS kernel partition it
    has chosen to boot, e.g. **root=PARTUUID=%U/PARTNROFF=1** will set
    the root partition to the one after the booted partition.

    As knowing the currently booted partition is generally useful,
    **mkdepthcharge** prepends **kern_guid=%U** to the given kernel
    command line parameters to capture it. Use **--no-kern-guid** to
    disable this.

--keydir DIR
    Directory containing developer keys to use. Equivalent to using
    **--keyblock** "*DIR*\ **/kernel.keyblock**", **--signprivate**
    "*DIR*\ **/kernel_data_key.vbprivk**", and **--signpubkey**
    "*DIR*\ **/kernel_subkey.vbpubk**".

--keyblock FILE
    Kernel key block file. If not given, the test key files distributed
    with |vbutil_kernel| are used.

--no-kern-guid
    Don't prepend **kern_guid=%U** to kernel command-line parameters.

--signprivate FILE
    Private keys in .vbprivk format. If not given, the test key files
    distributed with |vbutil_kernel| are used.

--signpubkey FILE
    Public keys in .vbpubk format. If not given, the test key files
    distributed with |vbutil_kernel| are used.


EXIT STATUS
===========
In general, exits with zero on success and non-zero on failure.


FILES
=====
|VBOOT_DEVKEYS|
    Default devkeys directory containing test keys which might have
    been installed by |vbutil_kernel|.

|VBOOT_KEYBLOCK|
    Default kernel key block file used for signing the image.

|VBOOT_SIGNPUBKEY|
    Default public key used to verify signed images.

|VBOOT_SIGNPRIVATE|
    Default private key used for signing the image.


EXAMPLES
========
**mkdepthcharge** **-o** *depthcharge.img* */boot/vmlinuz*
    The simplest invocation possible. If tried on an ARM machine, the
    firmware might refuse to boot the output image since it doesn't have
    a dtb for the machine. Otherwise, even if the firmware runs the
    */boot/vmlinuz* binary, it might not correctly boot due to
    non-firmware causes (e.g. kernel panic due to not having a root).

**mkdepthcharge** **-o** *system.img* **--cmdline** *"root=/dev/mmcblk0p2"* **--compress** *lz4* **--** */boot/vmlinuz.gz* */boot/initrd.img* *rk3399-gru-kevin.dtb*
    A command someone using a Samsung Chromebook Plus (v1) might run on
    their machine to create a bootable image for their running system.


SEE ALSO
========
|mkimage|, |vbutil_kernel|, |futility|

