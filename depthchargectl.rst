.. SPDX-License-Identifier: GPL-2.0-or-later

.. depthcharge-tools depthchargectl(1) manual page
.. Copyright (C) 2019-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
.. See COPYRIGHT and LICENSE files for full copyright information.

==============
depthchargectl
==============

--------------------------------------------------
Manage the ChromeOS bootloader and its boot images
--------------------------------------------------

:date: 2023-06-30
:version: v0.6.2
:manual_section: 1
:manual_group: depthcharge-tools

.. |mkdepthcharge| replace:: *mkdepthcharge*\ (1)
.. |cgpt| replace:: *cgpt*\ (1)
.. |vbutil_kernel| replace:: *vbutil_kernel*\ (1)

.. |CONFIG_DIR| replace:: **/etc/depthcharge-tools**
.. |CONFIG_FILE| replace:: **/etc/depthcharge-tools/config**
.. |CONFIGD_DIR| replace:: **/etc/depthcharge-tools/config.d**
.. |IMAGES_DIR| replace:: **/boot/depthcharge**
.. |INITD_DIR| replace:: **/etc/init.d**
.. |SYSTEMD_DIR| replace:: **/usr/lib/systemd/system**
.. |USR_CMDLINE_FILE| replace:: **/usr/lib/kernel/cmdline**
.. |ETC_CMDLINE_FILE| replace:: **/etc/kernel/cmdline**
.. |PROC_CMDLINE_FILE| replace:: **/proc/cmdline**
.. |VBOOT_DEVKEYS| replace:: **/usr/share/vboot/devkeys**
.. |USR_KI_DIR| replace:: **/usr/lib/kernel/install.d**
.. |ETC_KI_CONF| replace:: **/etc/kernel/install.conf**


SYNOPSIS
========
**depthchargectl** [options] *COMMAND* ...

**depthchargectl bless** [options] [*PARTITION* | *DISK*]

**depthchargectl build** [options] [*KERNEL_VERSION*]

**depthchargectl check** [options] *IMAGE*

**depthchargectl config** [options] *KEY*

**depthchargectl list** [options] [*DISK* ...]

**depthchargectl remove** [options] (*KERNEL_VERSION* | *IMAGE*)

**depthchargectl target** [options] [*PARTITION* | *DISK* ...]

**depthchargectl write** [options] [*KERNEL_VERSION* | *IMAGE*]


DESCRIPTION
===========
**depthchargectl** automatically manages the ChromeOS bootloader by
building images for the current board and system, writing them to
appropriate ChromeOS kernel partitions, prioritizing those partitions
accordingly, and setting them as successful on boot. When you have more
than one ChromeOS kernel partition, they will be utilized in rotation so
that an unsuccessful boot attempt can revert to the last good version.

The *KERNEL_VERSION* argument is a distro-specific representation of a
kernel and usually is the latter part of **/boot/vmlinuz-**\ *VERSION*.
The *IMAGE* argument is a boot image for the ChromeOS bootloader, or a
file suspected to be one. *DISK* should be a physical disk containing a
GPT partition table (e.g. **/dev/mmcblk0**, **/dev/sda**), but virtual
disks (e.g. **/dev/dm-0**) are resolved to such physical disks if
possible. *PARTITION* must be one of partition devices of a physical
disk (e.g **/dev/mmcblk0p1**, **/dev/sda2**). The *vmlinuz*, *initramfs*
and *dtb* files are as explained in |mkdepthcharge|.

The program's functionality is divided into subcommands:

depthchargectl bless
--------------------
Sets bootloader-specific flags for a given partition or the currently
booted partition as detected from the **kern_guid=**\ *PARTUUID*
parameter |mkdepthcharge| adds to the kernel command line. By default,
this marks the partition as successfully booted and the most preferred
one, but can disable the partition or make it boot only on the next
attempt as well.

depthchargectl build
--------------------
Builds a bootable image from the running system for this board, using
the latest or a specific kernel version. **depthchargectl** keeps a
database of known ChromeOS boards and how to build bootable images for
them. For example, it keeps track of which device-tree file that needs
to be included for each ARM board. It also figures out distro-specific
information of where the *vmlinuz*, *initramfs* and *dtb* files are
located. It uses this information and |mkdepthcharge| to build this
image.

It automatically adds an appropriate **root=**\ *ROOT* kernel command
line parameter deduced from **/etc/fstab**. Higher compression levels
for the kernel are automatically tried as necessary, when the firmware
supports them.

depthchargectl config
---------------------
Retrieves the configured value for a given configuration key, primarily
for use in scripts that integrate **depthchargectl** with the system
upgrade process. Can also query information about boards.

depthchargectl check
--------------------
Checks if a file is a depthcharge image that can be booted on this
board. **depthchargectl** also keeps track of restrictions on images
for each board. For example, earlier ChromeOS board can boot images
up to a specific size, e.g. 32MiB. It checks if its input is in a format
the ChromeOS bootloader expects and satisfies these restrictions.

depthchargectl list
-------------------
Prints a table of ChromeOS kernel partitions and their bootloader
specific GPT flags (i.e. Successful, Priority, Tries). By default, it
only searches the physical disks on which the boot and root partitions
reside.

depthchargectl remove
---------------------
Disables partitions that contain a specific image or a specific kernel
version. This is most useful when you are removing a kernel version and
its modules from your system, and know images built with this kernel
will fail to boot from that point on.

depthchargectl target
---------------------
Chooses and prints the lowest priority, preferably unsuccessful ChromeOS
kernel partition to write a boot image to. By default, searches the same
disks as the **list** subcommand. If a partition is given, it checks if
it is an appropriate for a boot image. Tries to avoid the currently
booted kernel.

depthchargectl write
--------------------
Writes a specific image or builds and writes a *kernel-version* image to
a partition the **target** subcommand returns, and marks it as bootable
once on the next boot. The **bless** subcommand must be run after a
successful boot to make the partiiton permanently bootable, but that is
possible to do automatically with the service files provided with this
package.


OPTIONS
=======

Global options
--------------
-h, --help
    Show a help message and exit.

-v, --verbose
    Print info messages and |mkdepthcharge| output to stderr.

-V, --version
    Print program version and exit.

--root ROOT
    Root device or mountpoint of the system to work on. If a mounted
    device is given, its mountpoint is used. Defaults to the currently
    booted system's root.

--root-mountpoint DIR, --boot-mountpoint DIR
    Root and boot mountpoints of the system to work on. If not given,
    deduced from the **--root** argument. These are helpful because the
    **--root** argument is overloaded by the **build** subcommand, which
    adds it as a kernel command line argument, and it can be desirable
    to avoid that while building an image for a chroot.

--tmpdir DIR
    Directory to keep temporary files. Normally **depthchargectl**
    creates a temporary directory by itself and removes it when it
    quits. However, if a temporary directory is specified with this
    option any temporary files will be created under it and will not be
    deleted.

Configuration options
---------------------
In addition to its built-in configuration, **depthchargectl** reads
|CONFIG_FILE| and |CONFIGD_DIR|/*\ ** as configuration files to make it
adaptable to different boards and systems. The following options allow
this configuration to be overridden temporarily.

--config FILE
    Additional configuration file to read. This can include changing
    board properties or adding new boards, which mostly isn't possible
    to do with command-line options.

--board CODENAME
    Assume **depthchargectl** is running on the specified board. Normally
    it tries to detect which board it's running on primarily based on
    the HWID of the board set by the vendor, among other things.

--images-dir DIR
    Directory to store and look for built depthcharge images. By
    default, set to |IMAGES_DIR|.

--vboot-keyblock KEYBLOCK
    The kernel keyblock file required to sign and verify images. By
    default, **depthchargectl** searches for these keys in |CONFIG_DIR|
    and |VBOOT_DEVKEYS| directories.

--vboot-public-key SIGNPUBKEY
    The public key required to verify images, in .vbpubk format. By
    default, **depthchargectl** searches for these keys in |CONFIG_DIR|
    and |VBOOT_DEVKEYS| directories.

--vboot-private-key SIGNPRIVATE
    The private key necessary to sign images, in .vbprivk format. By
    default, **depthchargectl** searches for these keys in |CONFIG_DIR|
    and |VBOOT_DEVKEYS| directories.

--kernel-cmdline *CMD* [*CMD* ...]
    Command-line parameters for the kernel. By default, these are read
    from |ETC_CMDLINE_FILE|, |USR_CMDLINE_FILE| or |PROC_CMDLINE_FILE|.
    **depthchargectl** and |mkdepthcharge| may append some other values
    to this: an appropriate **root=**\ *ROOT*, the **kern_guid=%U**
    parameter required for the **bless** subcommand, **noinitrd** if
    **--ignore-initramfs** is given.

--ignore-initramfs
    Do not include *initramfs* in the built images, ignore the initramfs
    checks for the **root=**\ *ROOT* argument, and add **noinitrd** to
    the kernel cmdline. If you know that your OS kernel can boot on this
    board without an initramfs (perhaps because it has a built-in one),
    you can specify this option to build an initramfs-less image.

--zimage-initramfs-hack
    Choose which initramfs support hack will be used for the zimage
    format. Either **set-init-size** (the default), **pad-vmlinuz**
    for kernels without **KASLR**, or **none** if depthcharge ever
    gets native support for safely loading zimage initramfs.

depthchargectl bless options
----------------------------
--bad
    Set the specified partition as unbootable. This sets all three of
    the *Successful*, *Priority*, *Tries* flags to 0.

--oneshot
    Set the specified partition to be tried once in the next boot. This
    sets the *Successful* flag to 0, *Tries* flag to 1, and makes sure the
    *Priority* flag is the highest one among all the partitions of the
    disk the specified one is in.

-i NUM, --partno NUM
    Partition number in the given disk image, for when the positional
    argument is a disk image instead of a partition block device.

depthchargectl build options
----------------------------
--description DESC
    Human-readable description for the image. By default, a string that
    describes your system with the specified kernel release name, like
    "Debian GNU/Linux, with Linux 5.10.0-6-arm64".

--root ROOT
    Root device to add to kernel cmdline. By default, this is acquired
    from **/etc/fstab** or a filesystem UUID is derived from the mounted
    root. If **none** is passed, no root parameter is added.

--compress *TYPE* [*TYPE* ...]
    Compression types to attempt. By default, all compression types that
    the board supports based on **depthchargectl** configuration are
    attempted from lowest to highest compression.

--timestamp SECONDS
    Build timestamp for the image. By default, **SOURCE_DATE_EPOCH** is
    used if it's set. If not, the modification date of either the
    *initramfs* or *vmlinuz* is used as an attempt to keep images somewhat
    reproducible.

-o PATH, --output PATH
    Output image to path instead of storing it in the images-dir.

The following options allow one to specify the exact files to be used in
building the image, instead of letting **depthchargectl** deduce them:

--kernel-release NAME
    Release name for the kernel to be used in image filename under the
    images-dir (unless **--output** is specified).

--kernel FILE
    Kernel executable. Usually **/boot/vmlinuz-**\ *VERSION* by default,
    but depends on your OS.

--initramfs *FILE* [*FILE* ...]
    Ramdisk image. Usually **/boot/initrd.img-**\ *VERSION* by default,
    but depends on your OS. If **none** is passed, no initramfs is
    added.

--fdtdir DIR
    Directory to search device-tree binaries for the board. Usually
    **/boot/dtbs** or a directory like **/usr/lib/linux-image-**\
    *VERSION*, depends on your OS. *dtb* files in this dir are searched
    to find ones matching your board's device-tree compatible string set
    in configuration.

--dtbs *FILE* [*FILE* ...]
    Device-tree binary files to use instead of searching *fdtdir*.

depthchargectl config options
-----------------------------
--section SECTION
    Config section to retrieve configured values from. By default, this
    is the globally default section: **depthcharge-tools**.

--default DEFAULT
    A default value to return if the given config key doesn't exist in
    the given config section. If a default value is not given, this
    subcommand prints an error message and exits with nonzero status
    when the key is missing.

depthchargectl check options
----------------------------
This subcommand takes no specific options.

depthchargectl list options
---------------------------
-a, --all-disks
    List partitions on all disks.

-c, --count
    Print only the count of partitions.

-n, --noheadings
    Don't print column headings.

-o COLUMNS, --output COLUMNS
    Comma separated list of columns to output. Supported columns are
    **ATTRIBUTE** (or **A**), **SUCCESSFUL** (or **S**), **TRIES** (or
    **T**), **PRIORITY** (or **P**) for ChromeOS GPT flags, **PATH** for
    the partition device (if exists), **DISKPATH** (or **DISK**) for the
    disk device/image the partition is in, **PARTNO** for the partition
    number, and **SIZE** for the partition size in bytes.

depthchargectl remove options
-----------------------------
-f, --force
     Allow disabling the currently booted partition.

depthchargectl target options
-----------------------------
-a, --all-disks
    Consider all available disks, instead of considering only disks
    containing the root and boot partitions.

--allow-current
    Allow targeting the currently booted partition.

-s BYTES, --min-size BYTES
    Only consider partitions larger than this size in bytes. Defaults to
    **64 KiB** to ignore unused partitions in ChromeOS installations.

depthchargectl write options
----------------------------
--allow-current
    Allow overwriting the currently booted partition.

-f, --force
    Write image to disk even if it cannot be verified by the **check**
    subcommand.

--no-prioritize
    Don't modify ChromeOS GPT flags on the partition. Normally, the
    flags would be set to make the system boot from the newly written
    partition on the next boot.

-t DEVICE, --target DEVICE
    Specify a disk or partition device to write to. This device is
    passed to the **target** subcommand to determine where exactly to
    write to.


EXIT STATUS
===========
In general, exits with zero on success and non-zero on failure. Some
subcommands return more specified exit statuses:

depthchargectl build exit status
--------------------------------

0
    Image built and stored successfully.

1
    An error occurred before or during building the image.

3
    Can build an image with an *initramfs*, but it is too big for the
    board despite using maximum allowed kernel compression. This might
    be solvable by reducing the *initramfs* size.

4
    Like **3**, but without an *initramfs* or reducing the *initramfs*
    size wouldn't make things fit. This might be solvable by reducing
    the *vmlinuz* size, perhaps by building a custom kernel.

depthchargectl check exit status
--------------------------------

0
    The *image* passes all checks.

1
    Errors unrelated to image checks.

2
    The *image* isn't a readable file.

3
    Size of the *image* is too big for the board.

4
    The *image* cannot be interpreted by |vbutil_kernel|.

5
    The *image* fails the |vbutil_kernel| signature checks.

6
    The *image* is built with a wrong format for the board.

7
    The *image* is missing device-tree files compatible with the board.

depthchargectl target exit status
---------------------------------

0
    A usable *partition* is given, or a usable partition was chosen from
    *disk*\ s. The partition passes the checks and is printed to output.

1
    Errors unrelated to partition checks.

2
    The *partition* is not a writable block device.

3
    The disk containing the *partition* is not a writable block device.

4
    Cannot parse a partition number from the *partition*.

5
    The *partition* is not a ChromeOS kernel partition.

6
    The *partition* is the currently booted partition.

7
    The *partition* is smaller than the **--min-size** argument.


FILES
=====
|CONFIG_DIR|
    Configuration directory. **depthchargectl** searches this directory
    for configuration files and ChromiumOS verified boot keys.

|CONFIG_FILE|
    System configuration file. The "Configuration options" explained
    above can be set here to have them as long-term defaults. It's also
    possible to modify board properties or add new boards here.

|CONFIGD_DIR|/*\ **
    These files are considered appended to the **config** file.

|ETC_CMDLINE_FILE|, |USR_CMDLINE_FILE|, |PROC_CMDLINE_FILE|
    Files from which **depthchargectl** may deduce a default kernel
    command line.

|SYSTEMD_DIR|\ **/depthchargectl-bless.service**
    A systemd service that runs **depthchargectl bless** on successful
    boots.

|USR_KI_DIR|\ **/90-depthcharge-tools.install**
    A systemd kernel-install plugin that can automatically manage your
    system if **layout=depthcharge-tools** is set in |ETC_KI_CONF|.

|INITD_DIR|\ **/depthchargectl-bless**
    An init service that runs **depthchargectl bless** on successful
    boots.

|VBOOT_DEVKEYS|
    A directory containing test keys which should have been installed by
    |vbutil_kernel|. **depthchargectl** also searches this directory if
    no verified boot keys are set in configuration or found in config
    directories.

|IMAGES_DIR|/*\ **\ **.img**
    The most recently built images for each kernel version.


EXAMPLES
========
**depthchargectl** **list** **-n** **-o** *PATH*
    Get a list of partitions **depthchargectl** will act on by default.

**depthchargectl** **build** **--board** *kevin* **--root** */mnt* **--output** *depthcharge.img*
    Build an image for the Samsung Chromebook Plus (v1), using files
    from and intended to boot with the chroot system mounted at */mnt*.

**depthchargectl** **config** *board*
    Print the board codename for the detected board.

**depthchargectl** **config** **--default** *False* *enable-system-hooks*
    Print the *enable-system-hooks* config if it's set, *False* if not.
    This specific config key is meant to be a common mechanism which
    distro packagers can use to let users disable system upgrade hooks
    that use depthchargectl.

**depthchargectl** **write** **--allow-current**
    Build, check and write an image for the latest *kernel-version* of
    this system to disk while allowing overwriting the currently booted
    partiiton. You might use this if you only have a single ChromeOS
    kernel partition, but broken kernels might make your system
    unbootable.

**depthchargectl** **write** *vmlinux.kpart* **-t** */dev/mmcblk1p1*
    Write the **vmlinux.kpart** file to **/dev/mmcblk1p1**, only if both
    the image and the partition are valid. Something of this form would
    be used for writing images to a secondary or external disk.

SEE ALSO
========
|mkdepthcharge|, |cgpt|, |vbutil_kernel|
