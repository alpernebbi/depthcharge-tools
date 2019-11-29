# This file is sourced by depthchargectl.
PROG="depthchargectl target"
usage() {
cat <<EOF
Usage:
 depthchargectl target [options] [partition | disk ...]

Choose or validate a ChromeOS Kernel partition to use.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -s, --min-size BYTES       Target partitions larger than this size.
     --allow-current        Allow targeting the currently booted part.
EOF
}


# Parse options and arguments
# ---------------------------

set_target() {
    if [ -n "${1:-}" ]; then
        info "Targeting disk or partition: $1"
        TARGETS="${TARGETS:-}${TARGETS:+,}${1}"
    fi
}

# Should return number of elemets to shift, never zero.
cmd_args() {
    case "$1" in
        # Options:
        -s|--min-size)      MIN_SIZE="$2";      return 2 ;;
        --allow-current)    ALLOW_CURRENT=yes;  return 1 ;;

        # End of options.
        -*) usage_error "Option '$1' not understood." ;;
        *)  set_target "$1"; return 1 ;;
    esac
}


# Set argument defaults
# ---------------------

cmd_defaults() {
    # Can be empty (for auto), but needs to be set.
    : "${TARGETS:=}"

    # Disable size checking by default.
    : "${MIN_SIZE:=0}"

    # Disallow targeting currently booted partition by default.
    : "${ALLOW_CURRENT:=no}"

    readonly TARGETS MIN_SIZE ALLOW_CURRENT
}


# Find and check target partitions
# --------------------------------

set_part() {
    if [ -n "${PART:-}" ]; then
        error "Can't have multiple partitions ('$PART', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        PART="$1"
    fi
}

add_disk() {
    if [ -n "${1:-}" ]; then
        DISKS="${DISKS:-}${DISKS:+,}${1}"
    fi
}

# Get the least-successful, least-priority, least-tries-left partition
# in that order of preference. Can take disks-to-search as arguments.
worst_partition() {
    depthcharge_parts_table "$@" | {
        # Ignore partitions smaller than the minimum.
        while read -r S P T size dev; do
            if [ "$size" -gt "${MIN_SIZE:-0}" ]; then
                printf "%d %d %d %s\n" "$S" "$P" "$T" "$dev"
            else
                warn "Ignoring part '$dev' smaller than '$MIN_SIZE' bytes."
            fi
        done
    } | sort | head -1 | cut -d' ' -f4
}

check_part_writable() {
    info "Checking if targeted partition is writable."
    if [ ! -b "${1:-$PART}" ]; then
        error "Target '${1:-$PART}' is not a valid block device." || :
        return 2
    elif [ ! -w "${1:-$PART}" ]; then
        error "Target '${1:-$PART}' is not writable." || :
        return 2
    fi
}

check_disk_writable() {
    info "Checking if targeted partition's disk is writable."
    disk="$(disk_from_partdev "${1:-$PART}")"
    if [ ! -b "$disk" ]; then
        error "Target disk '$disk' is not a valid block device." || :
        return 3
    elif [ ! -w "$disk" ]; then
        error "Target disk '$disk' is not writable." || :
        return 3
    fi
}

check_integer_partno() {
    info "Checking if we can parse targeted partition's partition number."
    partno="$(partno_from_partdev "${1:-$PART}")"
    case "$partno" in
        *[!0-9]*)
            error "Parsed invalid partition no for '${1:-$PART}'." || :
            return 4
            ;;
    esac
}

check_type_guid() {
    info "Checking if targeted partition's type is ChromeOS kernel."
    disk="$(disk_from_partdev "${1:-$PART}")"
    partno="$(partno_from_partdev "${1:-$PART}")"
    typeguid="$(cgpt_ show -i "$partno" -t "$disk")"
    if [ "$typeguid" != "FE3A2A5D-4F32-41A7-B725-ACCC3285A309" ] \
    && [ "$typeguid" != "fe3a2a5d-4f32-41a7-b725-accc3285a309" ]; then
        error "Partition '${1:-$PART}' is not of type ChromeOS kernel." || :
        return 5
    fi
}

check_current() {
    info "Checking if targeted partition is currently booted one."
    current="$(cgpt_ find -1 -u "$(get_kern_guid)")"
    if [ "${1:-$PART}" = "$current" ]; then
        error "Partition '${1:-$PART}' is the currently booted partition." \
            || :
        return 6
    fi
}

check_min_size() {
    info "Checking if targeted partition is bigger than given minimum size."
    size="$(blockdev --getsize64 "${1:-$PART}")"
    if [ "$size" -le "${MIN_SIZE:-0}" ]; then
        error "Partition '${1:-$PART}' smaller than '${MIN_SIZE:-0}' bytes." \
            || :
        return 7
    fi
}

cmd_main() {
    if [ -z "${TARGETS:-}" ]; then
        # Disks containing /boot and / should be available during boot,
        # so we target only them by default.
        info "Identifying disks containing root and boot partitions."
        DISKS="$(bootable_disks)" \
            || error "Couldn't find a real disk containing root or boot."
    else
        IFS="${ORIG_IFS},"
        set -- $TARGETS
        IFS="$ORIG_IFS"

        for target in "$@"; do
            if depthcharge_parts "$target" >/dev/null; then
                info "Using target '$target' as a disk."
                add_disk "$target"
            else
                info "Using target '$target' as a partition."
                set_part "$target"
            fi
        done
    fi
    readonly DISKS

    # Targeting disks and targeting parts are mutually exclusive.
    if [ -n "${PART:-}" ] && [ -n "${DISKS:-}" ]; then
        error "Cannot target both a disk and a partition."
    elif [ -z "${PART:-}" ] && [ -z "${DISKS:-}" ]; then
        error "Could not find a partition or a disk from targets '$TARGETS'."
    fi

    if [ -z "${PART:-}" ]; then
        IFS="${IFS},"
        set -- $DISKS
        IFS="$ORIG_IFS"

        info "Searching for ChromeOS kernel partitions on disks '$DISKS'."
        if PART="$(worst_partition "$@")" && [ -n "$PART" ]; then
            info "Chose partition '$PART' as the target partition."
        else
            error "No usable ChromeOS kernel part found on disks '$DISKS'."
        fi
    fi
    readonly PART

    check_part_writable "$PART"
    check_disk_writable "$PART"
    check_integer_partno "$PART"
    check_type_guid "$PART"

    if [ "$ALLOW_CURRENT" = "no" ]; then
        check_current "$PART"
    fi

    if [ "${MIN_SIZE:-0}" -gt 0 ]; then
        check_min_size "$PART"
    fi

    # Output the targeted partition.
    printf "%s\n" "$PART"
}

