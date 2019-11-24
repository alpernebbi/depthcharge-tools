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
 -t, --target DISK|PART     Specify a disk or partition to write to.
     --no-prioritize        Don't set any flags on the partition.
EOF
}


# Parse options and arguments
# ---------------------------

set_target() {
    if [ -n "${1:-}" ]; then
        info "Targeting disk or partition: $1"
        TARGET="${TARGET:-}${TARGET:+,}${1}"
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
    : "${TARGET:=}"

    readonly FORCE PRIORITIZE IMAGE TARGET
}


# Write image to partition
# ------------------------

# Get the least-successful, least-priority, least-tries-left partition
# in that order of preference. Can take disks-to-search as arguments.
worst_partition() {
    image_size="$(stat -c "%s" "$IMAGE")"
    depthcharge_parts_table "$@" | {
        # Ignore partitions smaller than the image.
        while read -r S P T size dev; do
            if [ "$size" -gt "$image_size" ]; then
                printf "%d %d %d %s\n" "$S" "$P" "$T" "$dev"
            else
                warn "Ignoring partition '$dev' smaller than image '$IMAGE'."
            fi
        done
    } | sort | head -1 | cut -d' ' -f4
}

set_target_part() {
    if [ -n "${TARGET_PART:-}" ]; then
        error "Can't have target partition multiple times" \
            "('$TARGET_PART', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        TARGET_PART="$1"
    fi
}

add_target_disk() {
    if [ -n "${1:-}" ]; then
        TARGET_DISKS="${TARGET_DISKS:-}${TARGET_DISKS:+,}${1}"
    fi
}

cmd_main() {
    if [ ! -r "$IMAGE" ]; then
        error "Depthcharge image '$IMAGE' not found or is not readable."
    fi

    if ! depthchargectl check "$IMAGE"; then
        error "Depthcharge image '$IMAGE' is not bootable on this machine."
    fi

    # Disks containing /boot and / should be available during boot,
    # so we can look there for a partition to write our boot image.
    if [ -z "${TARGET:-}" ]; then
        info "Identifying disks containing root and boot partitions."
        TARGET_DISKS="$(bootable_disks)" \
            || error "Couldn't find a real disk containing root or boot."
    else
        IFS="${IFS},"
        set -- $TARGET
        IFS="$ORIG_IFS"

        for target in "$@"; do
            if depthcharge_parts "$target" >/dev/null; then
                info "Using target '$target' as a disk."
                add_target_disk "$target"
            else
                info "Using target '$target' as a partition."
                set_target_part "$target"
            fi
        done
    fi
    readonly TARGET_DISKS

    # Targeting disks and targeting parts are mutually exclusive.
    if [ -n "${TARGET_PART:-}" ] && [ -n "${TARGET_DISKS:-}" ]; then
        error "Cannot target both a disk and a partition."
    elif [ -z "${TARGET_PART:-}" ] && [ -z "${TARGET_DISKS:-}" ]; then
        error "Could not find a partition or a disk from targets '$TARGET'."
    fi

    if [ -z "${TARGET_PART:-}" ]; then
        IFS="${IFS},"
        set -- $TARGET_DISKS
        IFS="$ORIG_IFS"

        info "Searching for ChromeOS kernel partitions on $TARGET_DISKS."
        TARGET_PART="$(worst_partition "$@")" \
            && [ -n "$TARGET_PART" ] \
            || error "No usable ChromeOS kernel part found on $TARGET_DISKS."
        info "Chose partition '$TARGET_PART' as the target partition."
    fi
    readonly TARGET_PART

    if [ ! -b "$TARGET_PART" ]; then
        error "Target '$TARGET_PART' is not a valid block device."
    elif [ ! -w "$TARGET_PART" ]; then
        error "Target '$TARGET_PART' is not writable."
    fi

    disk="$(disk_from_partdev "$TARGET_PART")"
    partno="$(partno_from_partdev "$TARGET_PART")"
    if [ ! -b "$disk" ]; then
        error "Target disk '$disk' is not a valid block device."
    elif [ ! -w "$disk" ]; then
        error "Target disk '$disk' is not writable."
    fi
    case "$partno" in
        *[!0-9]*) error "Parsed invalid partition no for '$TARGET_PART'." ;;
    esac

    typeguid="$(cgpt_ show -i "$partno" -t "$disk")"
    if [ "$typeguid" != "FE3A2A5D-4F32-41A7-B725-ACCC3285A309" ]; then
        error "Partition '$TARGET_PART' is not a ChromeOS kernel partition."
    fi

    current="$(cgpt_ find -1 -u "$(get_kern_guid)")"
    if [ "$TARGET_PART" = "$current" ]; then
        if [ "$FORCE" = "yes" ]; then
            warn "Overwriting the currently booted partition '$TARGET_PART'." \
                "This might make your system unbootable."
        else
            error "Refusing to overwrite the currently booted partition" \
                "'$TARGET_PART' as that might make your system unbootable."
        fi
    fi

    info "Writing depthcharge image '$IMAGE' to partition '$TARGET_PART':"
    dd if="$IMAGE" of="$TARGET_PART" status=none \
        || error "Failed to write image '$IMAGE' to partition '$TARGET_PART'."

    if [ "${PRIORITIZE:-yes}" = "yes" ]; then
        info "Setting '$TARGET_PART' as the highest-priority bootable part."
        cgpt_ add -i "$partno" -P 1 -T 1 -S 0 "$disk" \
            || error "Failed to set partition '$TARGET_PART' as bootable."
        cgpt_ prioritize -i "$partno" "$disk" \
            || error "Failed to prioritize partition '$TARGET_PART'."
    fi

}
