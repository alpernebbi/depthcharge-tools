# This file is sourced by depthchargectl.

usage() {
cat <<EOF
Usage:
 depthchargectl write [options] image

Write an image to a ChromeOS kernel partition.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -f, --force                Allow overwriting the current partition.
 -t, --target PARTITION     Specify a partition to write the image to.
 -T, --target-disk DISK     Specify disks to choose a partition from.
     --no-prioritize        Don't set any flags on the partition.
EOF
}


# Parse options and arguments
# ---------------------------

set_target() {
    if [ -n "${TARGET:-}" ]; then
        usage_error "Can't have target multiple times ('$TARGET', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        info "Targeting partition: $1"
        TARGET="$1"
    fi
}

add_disk() {
    if [ -n "${1:-}" ]; then
        info "Searching disk: $1"
        DISKS="${DISKS:-}${DISKS:+,}${1}"
    fi
}

set_image() {
    if [ -n "${IMAGE:-}" ]; then
        usage_error "Can't have image multiple times ('$IMAGE', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        info "Using image: $1"
        IMAGE="$1"
    fi
}

# Should return number of elemets to shift, never zero.
cmd_args() {
    case "$1" in
        # Options:
        -f|--force)         FORCE=yes;          return 1 ;;
        -t|--target)        set_target "$2";    return 2 ;;
        -T|--target-disk)   add_disk "$2";      return 2 ;;
        --no-prioritize)    PRIORITIZE=no;      return 1 ;;

        # End of options.
        -*) usage_error "Option '$1' not understood." ;;
        *)  set_image "$1"; return 1 ;;
    esac
}


# Set argument defaults
# ---------------------

cmd_defaults() {
    # Don't replace the currently booted partition.
    : "${FORCE:=no}"

    # Set priority to max (in disk) and tries to one.
    : "${PRIORITIZE:=yes}"

    # Mandatory argument.
    if [ -z "${IMAGE:-}" ]; then
        usage_error "Input file image is required."
    fi

    # Can be empty (for auto), but needs to be set.
    : "${DISKS:=}"
    : "${TARGET:=}"

    readonly FORCE PRIORITIZE IMAGE
}


# Write image to partition
# ------------------------

# Get the least-successful, least-priority, least-tries-left partition
# in that order of preference. Can take disks-to-search as arguments.
worst_partition() {
    depthcharge_parts_table "$@" | sort | head -1 | {
        read S P T dev && printf "%s" "$dev";
    }
}

cmd_main() {
    if [ ! -r "$IMAGE" ]; then
        error "Depthcharge image '$IMAGE' not found or is not readable."
    fi

    # TODO: valid image check

    # TODO: machine size check

    # Disks containing /boot and / should be available during boot,
    # so we can look there for a partition to write our boot image.
    if [ -z "${TARGET:-}" ] && [ -z "${DISKS:-}" ]; then
        info "Identifying disks containing root and boot partitions."
        DISKS="$(bootable_disks)" \
            || error "Couldn't find a real disk containing root or boot."
    fi
    readonly DISKS

    IFS="${IFS},"
    set -- $DISKS
    IFS="$ORIG_IFS"

    if [ -z "${TARGET:-}" ]; then
        info "Searching for ChromeOS kernel partitions (on $DISKS)."
        TARGET="$(worst_partition "$@")" \
            || error "No usable ChromeOS kernel partition found on $DISKS."
        info "Chose partition '$TARGET' as the target partition."
    fi
    readonly TARGET

    if [ ! -b "$TARGET" ]; then
        error "Target '$TARGET' is not a valid block device."
    elif [ ! -w "$TARGET" ]; then
        error "Target '$TARGET' is not writable."
    fi

    disk="$(disk_from_partdev "$TARGET")"
    partno="$(partno_from_partdev "$TARGET")"
    if [ ! -b "$disk" ]; then
        error "Target disk '$disk' is not a valid block device."
    elif [ ! -w "$disk" ]; then
        error "Target disk '$disk' is not writable."
    fi
    case "$partno" in
        *[!0-9]*) error "Parsed invalid partition number for '$TARGET'." ;;
    esac

    # TODO: partition size check

    typeguid="$(cgpt_ show -i "$partno" -t "$disk")"
    if [ "$typeguid" != "FE3A2A5D-4F32-41A7-B725-ACCC3285A309" ]; then
        error "Partition '$TARGET' is not a ChromeOS kernel partition."
    fi

    # TODO: currently booted partition check

    info "Writing depthcharge image '$IMAGE' to partition '$TARGET':"
    dd if="$IMAGE" of="$TARGET" \
        || error "Failed to write image '$IMAGE' to partition '$TARGET'."

    if [ "${PRIORITIZE:-yes}" = "yes" ]; then
        info "Setting '$TARGET' as the highest-priority bootable partition."
        cgpt_ add -i "$partno" -T 1 -S 0 "$disk" \
            || error "Failed to set partition '$TARGET' as bootable."
        cgpt_ prioritize -i "$partno" "$disk" \
            || error "Failed to prioritize partition '$TARGET'."
    fi

}
