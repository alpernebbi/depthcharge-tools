# This file is sourced by depthchargectl.

usage() {
cat <<EOF
Usage:
 depthchargectl write [options] [kernel-version | image]

Write an image to a ChromeOS kernel partition.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -t, --target DISK|PART     Specify a disk or partition to write to.
     --no-prioritize        Don't set any flags on the partition.
     --allow-current        Allow overwriting the current partition.
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

set_image() {
    if [ -n "${IMAGE:-}" ]; then
        usage_error "Can't have image multiple times ('$IMAGE', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        info "Using image: $1"
        IMAGE="$1"
    fi
}

set_kversion() {
    if [ -n "${KVERSION:-}" ]; then
        usage_error "Can't have kernel version multiple times" \
            "('$KVERSION', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        info "Using kernel version: $1"
        KVERSION="$1"
    fi
}

set_source() {
    if [ -n "${KVERSION:-}" ] || [ -n "${IMAGE:-}" ]; then
        usage_error "Can't have multiple inputs " \
            "('${KVERSION:-$IMAGE}', '${1:-}'."
    elif [ -n "${1:-}" ]; then
        for kversion in $(kversions); do
            if [ "$kversion" = "$1" ]; then
                set_kversion "$1"
                return
            fi
        done
        set_image "$1"
    fi
}

# Should return number of elemets to shift, never zero.
cmd_args() {
    case "$1" in
        # Options:
        -t|--target)        set_target "$2";    return 2 ;;
        --no-prioritize)    PRIORITIZE=no;      return 1 ;;
        --allow-current)    ALLOW_CURRENT=yes;  return 1 ;;

        # End of options.
        -*) usage_error "Option '$1' not understood." ;;
        *)  set_source "$1"; return 1 ;;
    esac
}


# Set argument defaults
# ---------------------

cmd_defaults() {
    # Don't replace the currently booted partition.
    : "${FORCE:=no}"

    # Set priority to max (in disk) and tries to one.
    : "${PRIORITIZE:=yes}"

    # Can be empty (for latest kernel version), but needs to be set.
    : "${KVERSION:=}"
    : "${IMAGE:=}"

    # Can be empty (for auto), but needs to be set.
    : "${TARGETS:=}"

    # Disallow targeting currently booted partition by default.
    : "${ALLOW_CURRENT:=no}"

    readonly FORCE PRIORITIZE TARGETS ALLOW_CURRENT
}


# Write image to partition
# ------------------------

cmd_main() {
    if [ -z "$IMAGE" ]; then
        if [ -z "$KVERSION" ]; then
            KVERSION="$(kversions | head -1)"
        fi
        IMAGE="${IMAGES_DIR}/${KVERSION}.img"
    fi
    readonly KVERSION IMAGE

    if [ ! -r "$IMAGE" ]; then
        if [ -n "$KVERSION" ]; then
            info "No depthcharge image for '$KVERSION', building."
            if [ "$VERBOSE" = "yes" ]; then
                depthchargectl build --verbose "$KVERSION"
            else
                depthchargectl build "$KVERSION"
            fi
        else
            error "Depthcharge image '$IMAGE' not found or is not readable."
        fi
    fi

    if ! depthchargectl check "$IMAGE"; then
        if [ -n "$KVERSION" ]; then
            error "Depthcharge image for version '$KVERSION' ('$IMAGE')" \
                "is not bootable on this machine."
        else
            error "Depthcharge image '$IMAGE' is not bootable" \
                "on this machine."
        fi
    fi

    IFS="${ORIG_IFS},"
    set -- $TARGETS
    IFS="$ORIG_IFS"

    image_size="$(stat -c "%s" "$IMAGE")"
    info "Searching disks for a target partition."
    if [ "$VERBOSE" = "yes" ]; then
        TARGET_PART="$(
            depthchargectl target \
                --verbose \
                --allow-current \
                --min-size "$image_size" \
                "$@" \
        )"
    else
        TARGET_PART="$(
            depthchargectl target \
                --allow-current \
                --min-size "$image_size" \
                "$@" \
        )"
    fi
    readonly TARGET_PART

    if depthchargectl target "$TARGET_PART" >/dev/null; then
        info "Targeted partition '$TARGET_PART' is usable."
    elif [ "$?" -ne 6 ]; then
        error "Targeted invalid partition '$TARGET_PART'."
    elif [ "$ALLOW_CURRENT" = "yes" ]; then
        warn "Overwriting the currently booted partition '$TARGET_PART'." \
            "This might make your system unbootable."
    else
        error "Refusing to overwrite the currently booted partition" \
            "'$TARGET_PART' as that might make your system unbootable."
    fi

    disk="$(disk_from_partdev "$TARGET_PART")"
    partno="$(partno_from_partdev "$TARGET_PART")"

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
