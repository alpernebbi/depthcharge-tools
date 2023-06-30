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

:date: 2023-06-30
:version: v0.6.2
:manual_section: 1
:manual_group: depthcharge-tools

.. |depthchargectl| replace:: *depthchargectl*\ (1)
.. |mkimage| replace:: *mkimage*\ (1)
.. |vbutil_kernel| replace:: *vbutil_kernel*\ (1)
.. |futility| replace:: *futility*\ (1)

.. |CONFIG_DIR| replace:: **/etc/depthcharge-tools**
.. |CONFIG_FILE| replace:: **/etc/depthcharge-tools/config**
.. |CONFIGD_DIR| replace:: **/etc/depthcharge-tools/config.d**
.. |VBOOT_DEVKEYS| replace:: **/usr/share/vboot/devkeys**
.. |VBOOT_KEYBLOCK| replace:: **kernel.keyblock**
.. |VBOOT_SIGNPUBKEY| replace:: **kernel_subkey.vbpubk**
.. |VBOOT_SIGNPRIVATE| replace:: **kernel_data_key.vbprivk**

SYNOPSIS
========
**mkdepthcharge** **-o** *FILE* [options] [*VMLINUZ*] [*INITRAMFS* ...] [*DTB* ...]


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

-i *INITRAMFS* [*INITRAMFS* ...], --initramfs *INITRAMFS* [*INITRAMFS* ...]
    Ramdisk image. If multiple files are given (e.g. for CPU microcode
    updates), they are concatenated and used as a single file.

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

--pad-vmlinuz, --no-pad-vmlinuz
    Pad the *VMLINUZ* file so that the kernel's self-decompression has
    enough space to avoid overwriting the *INITRAMFS* file during boot.
    This has different defaults and behaviour depending on the image
    format, see explanations in their respective sections.

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

--pad-vmlinuz, --no-pad-vmlinuz
    Pad the *VMLINUZ* file so that the kernel's self-decompression has
    enough space to avoid overwriting the *INITRAMFS* file during boot.
    The necessary padding is calculated based on compressed and
    decompressed kernel sizes and the **--kernel-start** argument.

    On earliest boards U-Boot moves the *INITRAMFS* away to a safe place
    before running the *VMLINUZ*, and on ARM64 boards Depthcharge itself
    decompresses the *VMLINUZ* to a safe place. But 32-bit ARM boards
    with Depthcharge lack FIT ramdisk support and run the *VMLINUZ*
    in-place, so this initramfs support hack is necessary on those.

    This option is enabled by default when **--patch-dtbs** is given,
    use the **--no-pad-vmlinuz** argument to disable it.

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
    **--set-init-size**, or custom kernels to make the parts fit as
    described above.

    This is disabled by default in favour of **--set-init-size**, use
    the **--pad-vmlinuz** argument to enable it.

--set-init-size, --no-set-init-size
    Increase the **init_size** kernel boot parameter so that the
    kernel's self-decompression does not overwrite the *INITRAMFS* file
    during boot. The modified value is calculated based on values in the
    zImage header and the **--kernel-start** argument.

    This only works if the kernel has **KASLR** enabled (as is the
    default), because then the kernel itself tries to avoid overwriting
    the *INITRAMFS* during decompression. However it does not do this
    when first copying the *VMLINUZ* to the end of the decompression
    buffer. Increasing **init_size** shifts copy this upwards to avoid
    it overlapping *INITRAMFS*.

    If the *VMLINUZ* and *INITRAMFS* are small enough, they may fit
    before the first compressed copy's start. In this case changing the
    value is unnecessary and skipped.

    This is enabled by default, use the **--no-set-init-size** argument to
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

--kern-guid, --no-kern-guid
    Prepend **kern_guid=%U** to kernel command-line parameters. This is
    enabled by default, use the **--no-kern-guid** argument to disable
    it.

--keydir KEYDIR
    Directory containing verified boot keys to use. Equivalent to using
    **--keyblock** *KEYDIR*\/|VBOOT_KEYBLOCK|, **--signprivate**
    *KEYDIR*\/|VBOOT_SIGNPRIVATE|, and **--signpubkey** *KEYDIR*\
    /|VBOOT_SIGNPUBKEY|.

--keyblock FILE, --signprivate FILE, --signpubkey FILE
    ChromiumOS verified boot keys. More specifically: kernel key block,
    private keys in .vbprivk format, and public keys in .vbpubk format.

    If not given, defaults to files set in **depthcharge-tools**
    configuration. If those are not set, **mkdepthcharge** searches for
    these keys in |CONFIG_DIR| and |VBOOT_DEVKEYS| directories, the
    latter being test keys that may be distributed with |vbutil_kernel|.

    You can set these in **depthcharge-tools** configuration by the
    **vboot-keyblock**, **vboot-private-key** and **vboot-public-key**
    options under a **depthcharge-tools** config section.


EXIT STATUS
===========
In general, exits with zero on success and non-zero on failure.


FILES
=====
|CONFIG_FILE|, |CONFIGD_DIR|/*\ **
    The **depthcharge-tools** configuration files. These might be used
    to specify locations of the ChromiumOS verified boot keys as system
    configuration.

|CONFIG_DIR|
    The **depthcharge-tools** configuration directory. **mkdepthcharge**
    searches this directory for verified boot keys.

|VBOOT_DEVKEYS|
    A directory containing test keys which should have been installed by
    |vbutil_kernel|.

*KEYDIR*/|VBOOT_KEYBLOCK|
    Default kernel key block file used for signing the image.

*KEYDIR*/|VBOOT_SIGNPUBKEY|
    Default public key used to verify signed images.

*KEYDIR*/|VBOOT_SIGNPRIVATE|
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

**mkdepthcharge** **-o** *peach-pit.img* **-c** *"console=null"* **--ramdisk-load-address** *0x44000000* **--** *vmlinuz* *initramfs* *exynos5420-peach-pit.dtb* *exynos5420-peach-pit.dtb*
    Build an image intended to work on a Samsung Chromebook 2 (11").
    This board uses a custom U-Boot, so needs an explicit ramdisk load
    address. Its firmware has a bug with loading the device-tree file,
    so needs the file twice for the result to be actually bootable.

SEE ALSO
========
|depthchargectl|, |mkimage|, |vbutil_kernel|, |futility|

