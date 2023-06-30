#compdef depthchargectl
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl zsh completions
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

function _depthchargectl {
    _arguments -C \
        {-h,--help}'[Show a help message.]' \
        {-v,--verbose}'[Print more detailed output.]' \
        {-V,--version}'[Print program version.]' \
        --tmpdir'[Directory to keep temporary files.]:temp dir:_directories' \
        --root'[Root device or mountpoint of the system to work on]:root device:{_depthchargectl__root; _depthchargectl__disk}' \
        --root-mountpoint'[Root mountpoint of the system to work on]:root mountpoint:_directories' \
        --boot-mountpoint'[Boot mountpoint of the system to work on]:boot mountpoint:_directories' \
        --config'[Additional configuration file to read]:config file:_files' \
        --board'[Assume running on the specified board]:board codenames:{_depthchargectl__board;}' \
        --images-dir'[Directory to store built images]:images dir:_directories' \
        --vboot-keyblock'[Keyblock file to include in images]:keyblock file:_files' \
        --vboot-public-key'[Public key file to verify images]:vbpubk file:_files' \
        --vboot-private-key'[Private key file to include in images]:vbprivk file:_files' \
        --kernel-cmdline'[Command line options for the kernel]:kernel cmdline:{_depthchargectl__cmdline;}' \
        --ignore-initramfs'[Do not include initramfs in images]' \
        --zimage-initramfs-hack'[Initramfs support hack choice for zimage format]:zimage hack:(set-init-size pad-vmlinuz none)' \
        '1:command:(bless build config check list remove target write)' \
        '*::arg:->args' \
        ;

    case "$state:$line[1]" in
        args:bless)
            _arguments -S \
                --bad'[Set the partition as unbootable]' \
                --oneshot'[Set the partition to be tried once]' \
                {-i,--partno}'[Partition number in the given disk image]:number:()' \
                ':disk or partition:{_depthchargectl__disk}' \
                ;
            ;;
        args:build)
            _arguments -S \
                --description'[Human-readable description for the image]:image description:($(source /etc/os-release; echo "$NAME"))' \
                --root'[Root device to add to kernel cmdline]:root device:{_depthchargectl__root; _depthchargectl__disk}' \
                --compress'[Compression types to attempt]:compress:(none lz4 lzma)' \
                --timestamp'[Build timestamp for the image]:timestamp:($(date "+%s"))' \
                {-o,--output}'[Output image to path instead of storing in images-dir]:output path:_files' \
                --kernel-release'[Release name for the kernel used in image name]:kernel release:{_depthchargectl__kernel;}' \
                --kernel'[Kernel executable]:kernel:_files' \
                --initramfs'[Ramdisk image]:*:initramfs:_files' \
                --fdtdir'[Directory to search device-tree binaries for the board]:fdtdir:_directories' \
                --dtbs'[Device-tree binary files to use instead of searching fdtdir]:*:dtb files:_files' \
                ':kernel version:{_depthchargectl__kernel}' \
                ;
            ;;
        args:config)
            _arguments -S \
                --section'[Config section to work on.]' \
                --default'[Value to return if key does not exist in section.]' \
                ':config key:' \
                ;
            ;;
        args:check)
            _arguments -S \
                ':image file:_files' \
                ;
            ;;
        args:list)
            local outputspec='{_values -s , "description" "A" "ATTRIBUTE" "S" "SUCCESSFUL" "T" "TRIES" "P" "PRIORITY" "PATH" "DISKPATH" "DISK" "PARTNO" "SIZE"}'
            _arguments -S \
                {-n,--noheadings}'[Do not print column headings.]' \
                {-a,--all-disks}'[List partitions on all disks.]' \
                {-c,--count}'[Print only the count of partitions.]' \
                {-o,--output}'[Comma separated list of columns to output.]:columns:'"$outputspec" \
                '*::disk or partition:{_depthchargectl__disk}' \
                ;
            ;;
        args:remove)
            _arguments -S \
                {-f,--force}'[Allow disabling the current partition.]' \
                '::kernel version or image file:{_depthchargectl__kernel; _files}' \
                ;
            ;;
        args:target)
            _arguments -S \
                {-s,--min-size}'[Target partitions larger than this size.]:bytes:(8M 16M 32M 64M 128M 256M 512M)' \
                --allow-current'[Allow targeting the currently booted part.]' \
                {-a,--all-disks}'[Target partitions on all disks.]' \
                '*::disk or partition:{_depthchargectl__disk}' \
                ;
            ;;
        args:write)
            _arguments -S \
                {-f,--force}'[Write image even if it cannot be verified.]' \
                {-t,--target}'[Specify a disk or partition to write to.]:disk or partition:{_depthchargectl__disk}' \
                --no-prioritize'[Do not set any flags on the partition]' \
                --allow-current'[Allow overwriting the current partition]' \
                '::kernel version or image file:{_depthchargectl__kernel; _files}' \
                ;
            ;;
        *) : ;;
    esac

}

function _depthchargectl__kernel {
    if command -v linux-version >/dev/null 2>/dev/null; then
        local kversions=($(linux-version list))
        _describe 'kernel version' kversions
    else
        local script=(
            'from depthcharge_tools.utils.platform import installed_kernels;'
            'kernels = (k.release for k in installed_kernels());'
            'print(*sorted(filter(None, kernels)));'
        )
        local kversions=($(python3 -c "$script"))
        _describe 'kernel version' kversions
    fi
} 2>/dev/null

function _depthchargectl__disk {
    local disks=($(lsblk -o "PATH" -n -l)) 2>/dev/null
    _describe 'disk or partition' disks
} 2>/dev/null

function _depthchargectl__board {
    local script=(
        'import re;'
        'from depthcharge_tools import boards_ini;'
        'boards = re.findall("codename = (.+)", boards_ini);'
        'print(*sorted(boards));'
    )
    local boards=($(python3 -c "$script"))
    _describe 'board codenames' boards
} 2>/dev/null

function _depthchargectl__cmdline {
    local cmdline=($(cat /proc/cmdline | sed -e 's/\(cros_secure\|kern_guid\)[^ ]* //g'))
    _describe 'kernel cmdline' cmdline
} 2>/dev/null

function _depthchargectl__root {
    local root=($(findmnt --fstab -n -o SOURCE "/"))
    _describe root root
} 2>/dev/null

function _depthchargectl__boot {
    local boot=($(findmnt --fstab -n -o SOURCE "/boot"))
    _describe boot boot
} 2>/dev/null

_depthchargectl "$@"
