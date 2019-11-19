# Working with disk and partition devices
# ---------------------------------------

# Get a partition device from disk device and partition number.
partdev_from_disk_partno() {
    case "$1" in
        # mmcblk0 1 -> mmcblk0p1
        # nvme0n1 2 -> nvme0n1p2
        *[0-9]) echo "${1}p${2}" ;;
        # sda 3 -> sda3
        *) echo "${1}${2}" ;;
    esac
}

# Get disk device from a partition device.
disk_from_partdev() {
    case "$1" in
        # Don't consider mmcblk1rpmb, mmcblk1boot0 as partitions.
        *boot*|*rpmb*) echo "${1}" ;;
        # mmcblk0p1 -> mmcblk0
        # nvme0n1p2 -> nvme0n1
        *[0-9]p[0-9]*) echo "${1%p*}" ;;
        # sda1 -> sda,1
        *[0-9]) echo "${1%%[0-9]*}" ;;
        *) echo "${1}" ;;
    esac
}

# Get partition number from a partiiton device.
partno_from_partdev() {
    case "$1" in
        # Don't consider mmcblk1rpmb, mmcblk1boot0 as partitions.
        *boot*|*rpmb*) return 1 ;;
        # mmcblk0p1 -> 1
        # nvme0n1p2 -> 2
        *[0-9]p[0-9]*) echo "${1##*p}" ;;
        # sda1 -> 1
        *[0-9]) echo "${1##*[!0-9]}" ;;
        *) return 1 ;;
    esac
}

# This function takes some devices (e.g. /dev/sda, /dev/mapper/luks-*,
# /dev/dm-0, /dev/disk/by-partuuid/*), tries to find physical disks
# where they are on.
find_disks() {
    # Use real devices for all. Turns /dev/disk/** into /dev/*.
    for d in "$@"; do
        if [ -n "$d" ]; then
            set -- "$@" "$(readlink -f "$d")"
        fi
        shift
    done

    # We can have chains of VG-LV, dm-*, md*, *_crypt, so on. They can
    # resolve to multiple devices. So we keep a stack of devices to
    # search (in $@) and prepend new ones to run in the next cycle of
    # the loop. We also need to keep the results in a stack, so keep
    # them at the end divided with a separator.
    BREAK="{BREAK}"
    set -- "$@" "$BREAK"
    while [ "$#" -gt 0 ]; do
        if [ "$1" = "$BREAK" ]; then
            shift
            break
        else
            dev="$(basename "$1")"
            shift
        fi

        parent="$(readlink -f "/sys/class/block/${dev}/..")" || parent=''
        case "$parent" in
            # VG-LV, sda2_crypt e.g. doesn't exist in /sys/class/block,
            # so readlink fails. We check each dm device's name here to
            # find which dm-* device they actually are.
            '')
                for d in /sys/class/block/dm-*; do
                    d="$(basename "$d")"
                    if grep -qs "$dev" "/sys/class/block/${d}/dm/name"; then
                        set -- "$d" "$@"
                    fi
                done
                ;;
            # dm-* and md* reside on /sys/devices/virtual/block, and
            # have a "slaves" folder for partitions they are built on.
            */virtual/block)
                for d in "/sys/class/block/${dev}/slaves"/*; do
                    set -- "$(basename "$d")" "$@"
                done
                ;;
            # Real partitions e.g. /sys/devices/**/block/sda/sda2
            # but we need their parent, sda.
            */block/*)
                set -- "$(basename "$parent")" "$@"
                ;;
            # These are real disks we can use. Keep them after the
            # separator, without duplicates.
            */block)
                case "$@" in
                    *${BREAK}*${dev}*) continue ;;
                esac
                if [ -b "/dev/${dev}" ]; then
                    set -- "$@" "/dev/${dev}"
                fi
                ;;
            # I don't know what goes here, but let's try the parent.
            *)
                set -- "$(basename "$parent")" "$@"
                ;;
        esac
    done

    echo "$@"
}

# Print physical disks on which the /boot and / partitions exist.
bootable_disks() {
    boot="$(findmnt --fstab -M "/boot" --evaluate -n -o SOURCE)" || :
    root="$(findmnt --fstab -M "/" --evaluate -n -o SOURCE)"
    find_disks "$boot" "$root"
}


# Interacting with cgpt
# ---------------------

# Wrap cgpt to print output only on successful runs, because it prints
# the usage message to stdout on errors instead of stderr.
cgpt_() {
    # We would lose the error status if we piped this.
    output="$(cgpt "$@" 2>/dev/null)" || return 1

    # cgpt prints its output twice when called with no disk arguments
    # and output is redirected or captured so we need to deduplicate.
    if [ "${1:-}" = "find" ]; then
        printf "%s" "$output" | sort -u
    else
        printf "%s" "$output"
    fi
}

# Print a list of ChromeOS kernel partitions.
depthcharge_parts() {
    cgpt_ find -t kernel "$@"
}

# Print a table of ChromeOS kernel partitions along with their success
# flag, priority and remaining tries.
depthcharge_parts_table() {
    for partdev in $(depthcharge_parts "$@"); do
        partno="$(partno_from_partdev "$partdev")"
        disk="$(disk_from_partdev "$partdev")"

        # This returns a 16 bit number like 0x100, 0xFF, 0x0 which gives
        # us all three values at once.
        attr="$(cgpt_ show -A -i "$partno" "$disk")" || continue
        case "$attr" in
            0x?|0x??|0x???|0x????) : ;;
            *) continue ;;
        esac

        # The lowest four bits are priority, second-lowest four are
        # remaining tries, and the 9th bit is the successful bit.
        P="$((attr & 0xF))"
        T="$((attr >> 4 & 0xF))"
        S="$((attr >> 8 & 0x1))"

        printf "%-2d %-2d %-2d %-20s\n" "$S" "$P" "$T" "$partdev"
    done
}

