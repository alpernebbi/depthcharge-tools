==============
depthchargectl
==============

--------------------------------------------------
manage the ChromeOS bootloader and its boot images
--------------------------------------------------

.. |PACKAGENAME| replace:: depthcharge-tools
.. |VERSION| replace:: v0.3.0

:date: 2019-12-06
:version: |VERSION|
:manual_section: 8
:manual_group: |PACKAGENAME|

.. |mkdepthcharge| replace:: *mkdepthcharge*\ (1)
.. |cgpt| replace:: *cgpt*\ (1)
.. |vbutil_kernel| replace:: *vbutil_kernel*\ (1)

.. |PREFIX| replace:: /usr/local
.. |DATADIR| replace:: |PREFIX|/share
.. |SYSCONFDIR| replace:: |PREFIX|/etc
.. |LOCALSTATEDIR| replace:: |PREFIX|/var
.. |LIBDIR| replace:: |PREFIX|/lib


SYNOPSIS
========
**depthchargectl** [options] *COMMAND* ...

**depthchargectl build** [options] [*kernel-version*]

**depthchargectl check** [options] *image*

**depthchargectl partitions** [options] [*disk* ...]

**depthchargectl rm** [options] [*kernel-version* | *image*]

**depthchargectl set-good** [options]

**depthchargectl target** [options] [*partition* | *disk* ...]

**depthchargectl write** [options] [*kernel-version* | *image*]


DESCRIPTION
===========
**depthchargectl** automatically manages the ChromeOS bootloader by
building images for the current machine and system, writing them to
appropriate ChromeOS kernel partitions, prioritizing those partitions
accordingly, and setting them as successful on boot. When you have more
than one ChromeOS kernel partition, they will be utilized in rotation so
that an unsuccessful boot attempt can revert to the last good version.

The *kernel-version* argument is a distro-specific representation of a
kernel and usually is the latter part of **/boot/vmlinuz-**\ *VERSION*.
The *image* argument is a boot image for the ChromeOS bootloader, or a
file suspected to be one. *disk* should be a physical disk containing a
GPT partition table (e.g. **/dev/mmcblk0**, **/dev/sda**), but virtual
disks (e.g. **/dev/dm-0**) are resolved to such physical disks if
possible. *partition* must be one of partition devices of a physical
disk (e.g **/dev/mmcblk0p1**, **/dev/sda2**). The *vmlinuz*, *initramfs*
and *dtb* files are as explained in |mkdepthcharge|.

The program's functionality is divided into subcommands:

depthchargectl build
--------------------
Builds a bootable image from the running system for this machine, using
the latest or a specific kernel version. **depthchargectl** keeps a
database of known ChromeOS machines and how to build bootable images for
them. For example, it keeps track of which device-tree file that needs
to be included for each ARM machine. It also keeps distro-specific
information of where the *vmlinuz*, *initramfs* and *dtb* files are
located. It uses this information and |mkdepthcharge| to build this
image.

It automatically adds an appropriate **root=**\ *ROOT* kernel command
line parameter deduced from **/etc/fstab**. Higher compression levels
for the kernel are automatically tried as necessary, when the firmware
supports them. This subcommand also stores previously built images and
the inputs used to build them, and avoids rebuilding an image when a
valid cached version exists.

depthchargectl check
--------------------
Checks if a file is a depthcharge image that can be booted on this
machine. **depthchargectl** also keeps track of restrictions on images
for each machine. For example, most ChromeOS machines can boot images
up to a specific size, e.g. 32MiB. It checks if its input is in a format
the ChromeOS bootloader expects, and satisfies these restrictions.

depthchargectl partitions
-------------------------
Prints a table of ChromeOS kernel partitions and their ChromeOS specific
GPT flags (i.e. Successful, Priority, Tries). By default, it only
searches the physical disks on which the boot and root partitions
reside.

depthchargectl rm
-----------------
Disables partitions that contain a specific image or a specific kernel
version. This is most useful when you are removing a kernel version and
its modules from your machine, and know images built with this kernel
will fail to boot from that point on.

depthchargectl set-good
-----------------------
Sets the current partition partition as the highest priority successful
partition. The currently booted partition is detected from the
**kern_guid=**\ *PARTUUID* parameter |mkdepthcharge| adds to the kernel
command line by default.

depthchargectl target
---------------------
Chooses and prints the lowest priority, preferably unsuccessful ChromeOS
kernel partition to write a boot image to. By default, searches the same
disks as the **partitions** subcommand. If a partition is given, it
checks if it is an appropriate for a boot image. Tries to avoid the
currently booted kernel.

depthchargectl write
--------------------
Writes a specific image or builds and writes a *kernel-version* image to
a partition the **target** subcommand returns, and marks it as bootable
once on the next boot. The set-good subcommand must be run after a
successful boot to make the partiiton permanently bootable.


OPTIONS
=======

Global options
--------------
-h, --help
    Show a help message and exit.

-v, --verbose
    Print info messages and |mkdepthcharge| output to stderr.

--version
    Print program version and exit.

depthchargectl build options
----------------------------
-a, --all
    Rebuild images for all kernel versions, instead of just the latest
    version. If this option is used, *kernel-version* must not be given.

-f, --force
    Rebuild images even if a cached version exists and seems valid.

--reproducible
    Try to build a reproducible image. If **SOURCE_DATE_EPOCH** is set
    externally, it is used and this option is assumed. If it is not set,
    but this option is given, **SOURCE_DATE_EPOCH** is set to the
    modification date of the initramfs (or the vmlinuz if no initramfs
    is used).

depthchargectl check options
----------------------------
This subcommand takes no specific options.

depthchargectl partitions options
---------------------------------
-a, --all-disks
    List partitions on all disks.

-n, --noheadings
    Don't print column headings.

-o COLUMNS, --output COLUMNS
    Comma separated list of columns to output. Supported columns are
    **SUCCESSFUL** (or **S**), **TRIES** (or **T**), **PRIORITY** (or
    **P**) for ChromeOS GPT flags, **DEVICE** for the partition device,
    **SIZE** for the partition size in bytes.

depthchargectl rm options
-------------------------
-f, --force
     Allow disabling the currently booted partition.

depthchargectl set-good options
-------------------------------
This subcommand takes no specific options.

depthchargectl target options
-----------------------------
--allow-current
    Allow targeting the currently booted partition.

-s BYTES, --min-size BYTES
    Only consider partitions larger than this size in bytes.

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
    Image built and stored successfully, or a cached valid image exists.

1
    An error occurred before or during building the image.

2
    Can build an image, but it cannot be validated according to the
    **check** subcommand.

3
    Can build an image with an *initramfs*, but it is too big for this
    machine despite using maximum allowed kernel compression. This might
    be solvable by reducing the *initramfs* size.

4
    Like **3**, but without an *initramfs*. This might be solvable by
    reducing the *vmlinuz* size, perhaps by building a custom kernel.

depthchargectl check exit status
--------------------------------

0
    The *image* passes all checks.

1
    Errors unrelated to image checks.

2
    The *image* isn't a readable file.

3
    Size of the *image* is too big for this machine.

4
    The *image* cannot be interpreted by |vbutil_kernel|.

5
    The *image* fails the |vbutil_kernel| signature checks.

6
    The *image* is built with a wrong format for the machine.

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
|SYSCONFDIR|/|PACKAGENAME|/config
    Configuration file. The kernel command line can be set here, among
    other things. See its contents for more information on what can be
    set.

|SYSCONFDIR|/|PACKAGENAME|/config.d/*\ **
    These files are considered appended to the **config** file.

|SYSCONFDIR|/|PACKAGENAME|/userdb
    User-specified machine database file. If you are using a
    custom-built firmware, you can override settings for your machine.
    You can also add information about yet unsupported machines to test
    **depthchargectl** on them.

|SYSCONFDIR|/|PACKAGENAME|/userdb.d/*\ **
    These files are considered appended to the **userdb** file.

|DATADIR|/|PACKAGENAME|/db
    Machine database file. Contains information about ChromeOS devices,
    how to build images for them, and their limitations on images.

|LIBDIR|/systemd/system/depthchargectl-set-good.service
    A systemd service that runs the **set-good** subcommand on
    successful boots.


EXAMPLES
========
depthchargectl partitions -n -o DEVICE
    Get a list of partitions **depthchargectl** will act on by default.

depthchargectl write --allow-current
    Build, check and write an image for the latest *kernel-version* of
    this system to disk while allowing overwriting the currently booted
    partiiton. You might use this if you only have a single ChromeOS
    kernel partition, but broken kernels might make your system
    unbootable.

depthchargectl write vmlinux.kpart -t /dev/mmcblk1p1
    Write the **vmlinux.kpart** file to **/dev/mmcblk1p1**, only if both
    the image and the partition are valid. Something of this form would
    be used for writing images to a secondary or external disk.


SEE ALSO
========
|mkdepthcharge|, |cgpt|, |vbutil_kernel|
