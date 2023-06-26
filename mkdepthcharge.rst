.. SPDX-License-Identifier: GPL-2.0-or-later

.. depthcharge-tools mkdepthcharge(1) manual page
.. Copyright (C) 2019-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
.. See COPYRIGHT and LICENSE files for full copyright information.

=============
mkdepthcharge
=============

---------------------------------------------
Build boot images for the ChromeOS bootloader
---------------------------------------------

:date: 2022-11-24
:version: v0.6.1
:manual_section: 1
:manual_group: depthcharge-tools

.. |depthchargectl| replace:: *depthchargectl*\ (1)
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
format the ChromeOS bootloader expects. It also automates preprocessing
steps and initramfs support hacks that a user would have to do manually
or write a script for.

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
    Kernel executable. If a compressed file is given here, it is
    decompressed and its contents are used in its place.

-i INITRAMFS, --initramfs INITRAMFS
    Ramdisk image.

-b *DTB* [*DTB* ...], --dtbs *DTB* [*DTB* ...]
    Device-tree binary files.

Global options
--------------
-A ARCH, --arch ARCH
    Architecture to build the images for.  The following architectures
    are understood: **arm**, **arm64**, **aarch64** for ARM boards;
    **x86**, **x86_64**, **amd64** for x86 boards. If not given, the
    build architecture of the *VMLINUZ* file is used.

--format FORMAT
    Kernel image format to use, either **fit** or **zimage**. If not
    given, architecture-specific defaults are used.

    fit
        This is the default on ARM boards. The *VMLINUZ* and the
        optional *INITRAMFS*, *DTB* files are packaged into the
        Flattened Image Tree (FIT) format using |mkimage| and that is
        passed to |vbutil_kernel|.

    zimage
        This is the default for x86 boards. The *VMLINUZ* is passed
        mostly unmodified to |vbutil_kernel|, except for decompression
        and padding for self-decompression. The *INITRAMFS* file is
        passed as the **--bootloader** argument and the kernel header is
        modified to point to where it will be in memory. It does not
        support packaging *DTB* files.

-h, --help
    Show a help message and exit.

--kernel-start ADDR
    Start of the Depthcharge kernel buffer in memory. Depthcharge loads
    the packed data to a fixed physical address in memory, and some
    initramfs support hacks require this value to be known. This is
    exactly the board-specific **CONFIG_KERNEL_START** value in the
    Depthcharge source code and defaults to **0x100000** for the x86
    architecture.

-o FILE, --output FILE
    Write the image to *FILE*. The image isn't generated at the output,
    but copied to it from a temporary working directory. This option is
    mandatory.

--tmpdir DIR
    Create and keep temporary files in *DIR*. If not given, a temporary
    **mkdepthcharge-\*** directory is created in **/tmp** and removed at
    exit.

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

--patch-dtbs, --no-patch-dtbs
    Add **linux,initrd-start** and **linux,initrd-end** properties to
    the *DTB* files' **/chosen** nodes. Their values are based on the
    **--kernel-start** or the **--ramdisk-load-address** argument, one
    of which is required if this argument is given.

    These properties are normally added by Depthcharge, but 32-bit ARM
    Chromebooks were released with versions before FIT ramdisk support
    was introduced, so this initramfs support hack is necessary on
    those.

--ramdisk-load-address ADDR
    Add a **load** property to the FIT ramdisk subimage section. The
    oldest ARM Chromebooks use an old custom U-Boot that implements the
    same verified boot flow as Depthcharge. Its FIT ramdisk support
    requires an explicit load address for the ramdisk, which can be
    provided with this argument.

zImage image options
--------------------

--pad-vmlinuz, --no-pad-vmlinuz
    Pad the *VMLINUZ* file so that the kernel's self-decompression has
    enough space to avoid overwriting the *INITRAMFS* file during boot.
    The necessary padding is calculated based on values in the zImage
    header and the **--kernel-start** argument.

    If the *VMLINUZ* and *INITRAMFS* are small enough (about 16 MiB in
    total) they may fit between **--kernel-start** and the start of the
    decompression buffer. In this case the padding is unnecessary and
    not added.

    The padding is usually larger than the decompressed version of the
    kernel, so it results in unbootable images for older boards with
    small image size limits. For these, it is usually necessary to use
    custom kernels to make the parts fit as described above.

    This is enabled by default, use the **--no-pad-vmlinuz** argument to
    disable it.

Depthcharge image options
-------------------------
--bootloader FILE
    Bootloader stub for the very first Chromebooks that use H2C as their
    firmware. Beyond those, this field is ignored on the firmware side
    except as a ramdisk for the **multiboot** and **zbi** formats.

    If an *INITRAMFS* is given for the **zimage** format, it is placed
    here as part of an initramfs support hack for x86 boards. Otherwise,
    an empty file is used.

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

--kern-guid, --no-kern-guid
    Prepend **kern_guid=%U** to kernel command-line parameters. This is
    enabled by default, use the **--no-kern-guid** argument to disable
    it.

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
    The simplest invocation possible. If tried on an ARM board, the
    firmware might refuse to boot the output image since it doesn't have
    a dtb for the board. Otherwise, even if the firmware runs the
    */boot/vmlinuz* binary, it might not correctly boot due to
    non-firmware causes (e.g. kernel panic due to not having a root).

**mkdepthcharge** **-o** *system.img* **--cmdline** *"root=/dev/mmcblk0p2"* **--compress** *lz4* **--** */boot/vmlinuz.gz* */boot/initrd.img* *rk3399-gru-kevin.dtb*
    A command someone using a Samsung Chromebook Plus (v1) might run on
    their board to create a bootable image for their running system.

**mkdepthcharge** **-o** *veyron.img* **-c** *"root=LABEL=ROOT gpt"* **--kernel-start** *0x2000000* **--patch-dtbs** **--** */boot/vmlinuz* */boot/initramfs-linux.img* */boot/dtbs/rk3288-veyron-\*.dtb*
    Build an image intended to work on veyron boards like ASUS
    Chromebook C201PA and Chromebook Flip C100PA. The stock Depthcharge
    on these boards doesn't process the FIT ramdisk, so the dtbs needs
    to be patched to boot with initramfs.

**mkdepthcharge** **-o** *peach-pit.img* **-c** *"console=null"* **--ramdisk-load-address** *0x44000000* **--** *vmlinuz* *initramfs* *exynos5420-peach-pit.dtb*
    Build an image intended to work on a Samsung Chromebook 2 (11").
    This board uses a custom U-Boot, so needs an explicit ramdisk load
    address.

SEE ALSO
========
|depthchargectl|, |mkimage|, |vbutil_kernel|, |futility|

