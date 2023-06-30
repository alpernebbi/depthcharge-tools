#compdef mkdepthcharge
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools mkdepthcharge zsh completions
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

function _mkdepthcharge {
    _arguments -S \
        {-d,--vmlinuz}'[Kernel executable]:vmlinuz file:_files' \
        {-i,--initramfs}'[Ramdisk image]:*:initrd files:_files' \
        {-b,--dtbs}'[Device-tree binary files]:*:dtbs files:_files' \
        {-h,--help}'[Show a help message.]' \
        {-v,--verbose}'[Print more detailed output.]' \
        {-V,--version}'[Print program version.]' \
        --tmpdir'[Directory to keep temporary files.]:temp dir:_directories' \
        --kernel-start'[Start of depthcharge kernel buffer in memory.]:kernel start:_numbers' \
        {-o,--output}'[Write resulting image to FILE.]:output:_files' \
        {-A,--arch}'[Architecture to build for.]:arch:(arm arm64 aarch64 x86 x86_64 amd64)' \
        --format'[Kernel image format to use.]:format:(fit zimage)' \
        {-C,--compress}'[Compress vmlinuz with lz4 or lzma.]:compression:(none lz4 lzma)' \
        {-n,--name}'[Description of vmlinuz to put in the FIT.]:description:($(source /etc/os-release; echo "$NAME"))' \
        --ramdisk-load-address'[Add load address to FIT ramdisk image section.]:ramdisk load address:_numbers' \
        --patch-dtbs'[Add linux,initrd properties to device-tree binary files.]' \
        --no-patch-dtbs'[Do not add linux,initrd properties to device-tree binary files.]' \
        --pad-vmlinuz'[Pad the vmlinuz file for safe decompression]' \
        --no-pad-vmlinuz'[Do not pad the vmlinuz file for safe decompression]' \
        --set-init-size'[Set init-size boot param for safe decompression]' \
        --no-set-init-size'[Do not set init-size boot param for safe decompression]' \
        '*'{-c,--cmdline}'[Command-line parameters for the kernel.]:*:kernel cmdline:{_mkdepthcharge__cmdline}' \
        --kern-guid'[Prepend kern_guid=%U to the cmdline.]' \
        --no-kern-guid'[Do not prepend kern_guid=%U to the cmdline.]' \
        --bootloader'[Bootloader stub binary to use.]:bootloader file:_files' \
        --keydir'[Directory containing vboot keys to use.]:keys dir:_directories' \
        --keyblock'[The key block file (.keyblock).]:keyblock file:_files' \
        --signprivate'[Private key (.vbprivk) to sign the image.]:vbprivk file:_files' \
        --signpubkey'[Public key (.vbpubk) to verify the image.]:vbpubk file:_files' \
        ':vmlinuz file:_files' \
        '*:initrd or dtb files:_files' \
        ;
}

function _mkdepthcharge__cmdline {
    local cmdline=($(cat /proc/cmdline | sed -e 's/\(cros_secure\|kern_guid\)[^ ]* //g'))
    _describe 'kernel cmdline' cmdline
} 2>/dev/null

_mkdepthcharge "$@"
