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

