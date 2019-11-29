# This file is sourced by depthchargectl.
PROG="depthchargectl write"
usage() {
cat <<EOF
Usage:
 depthchargectl write [options] [kernel-version | image]

Write an image to a ChromeOS kernel partition.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -f, --force                Write image even if it cannot be verified.
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
        -f|--force)         FORCE=yes;          return 1 ;;
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
    # Collect arguments for depthchargectl build.
    set --

    # No image given, try creating one.
    if [ -z "$IMAGE" ]; then
        if [ -n "$KVERSION" ]; then
            set -- "$KVERSION" "$@"
        fi
        if [ "$VERBOSE" = "yes" ]; then
            set -- "--verbose" "$@"
        fi
        IMAGE="$(depthchargectl build "$@")" \
            || error "Couldn't build an image to write."
    fi
    readonly KVERSION IMAGE

    # Collect arguments for depthchargectl check.
    set --
    if [ "$VERBOSE" = "yes" ]; then
        set -- "--verbose" "$@"
    fi

    # This also checks if the machine is supported.
    if depthchargectl check "$@" "$IMAGE"; then
        info "Depthcharge image '$IMAGE' is usable."
    elif [ "${FORCE:-no}" = "yes" ]; then
        warn "Depthcharge image '$IMAGE' is not bootable on this machine," \
            "continuing due to --force."
    else
        error "Depthcharge image '$IMAGE' is not bootable on this machine."
    fi

    # Collect arguments for depthchargectl target.
    IFS="${ORIG_IFS},"
    set -- $TARGETS
    IFS="$ORIG_IFS"

    if [ "$VERBOSE" = "yes" ]; then
        set -- "--verbose" "$@"
    fi

    # We don't want to abort if current partition is targeted since we
    # will handle that error here. But the partition must be bigger than
    # the image we'll write to it.
    info "Searching disks for a target partition."
    TARGET_PART="$( \
        depthchargectl target \
            --allow-current \
            --min-size "$(stat -c "%s" "$IMAGE")" \
            "$@" \
    )" || error "Couldn't find a usable partition to write to."
    readonly TARGET_PART

    # Check again without --allow-current to see if we targeted the
    # currently booted partition.
    if depthchargectl target "$TARGET_PART" >/dev/null 2>/dev/null; then
        info "Targeted partition '$TARGET_PART' is usable."
    elif [ "$?" -ne 6 ]; then
        # This case shouldn't happen as the previous call should've
        # failed and caused an exit (unless errexit was ignored).
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

    if [ -n "$KVERSION" ]; then
        msg "Wrote image for kernel version '$kversion' to '$TARGET_PART'."
    else
        msg "Wrote image '$IMAGE' to '$TARGET_PART'."
    fi

    if [ "${PRIORITIZE:-yes}" = "yes" ]; then
        info "Setting '$TARGET_PART' as the highest-priority bootable part."
        cgpt_ add -i "$partno" -P 1 -T 1 -S 0 "$disk" \
            || error "Failed to set partition '$TARGET_PART' as bootable."
        cgpt_ prioritize -i "$partno" "$disk" \
            || error "Failed to prioritize partition '$TARGET_PART'."
        msg "Set '$TARGET_PART' as next to boot."
    fi
}
