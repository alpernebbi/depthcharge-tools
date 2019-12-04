# This file is sourced by depthchargectl.
PROG="depthchargectl check"
usage() {
cat <<EOF
Usage:
 depthchargectl check [options] image

Check if a depthcharge image can be booted on the current system.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
EOF
}


# Parse options and arguments
# ---------------------------

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
        # No options.
        -*) usage_error "Option '$1' not understood." ;;
        *)  set_image "$1"; return 1 ;;
    esac
}


# Set argument defaults
# ---------------------

cmd_defaults() {
    # Mandatory argument.
    if [ -z "${IMAGE:-}" ]; then
        usage_error "Input file image is required."
    fi

    readonly IMAGE
}


# Check if image is bootable
# --------------------------

check_readable() {
    if [ ! -r "${1:-$IMAGE}" ]; then
        error "Depthcharge image '${1:-$IMAGE}' is not readable." || :
        return 2
    fi
}

check_size() {
    info "Checking if image fits into size limit."
    if [ "${MACHINE_MAX_SIZE:-0}" -gt 0 ]; then
        size="$(stat -c '%s' "${1:-$IMAGE}")"
        if [ "$size" -gt "${MACHINE_MAX_SIZE}" ]; then
            error "Depthcharge image size too big for this machine." || :
            return 3
        fi
    fi
}

check_depthcharge_image() {
    info "Checking depthcharge image validity."
    if ! futility vbutil_kernel >/dev/null 2>&1 \
        --verify "${1:-$IMAGE}"
    then
        error "Image couldn't be interpreted by vbutil_kernel." || :
        return 4
    fi
}

check_signature() {
    info "Checking depthcharge image signatures."
    if ! futility vbutil_kernel >/dev/null 2>&1 \
            --signpubkey "$CONFIG_VBOOT_SIGNPUBKEY" \
            --verify "${1:-$IMAGE}"
    then
        error "Depthcharge image not signed by configured keys." || :
        return 5
    fi
}

check_fit_format() {
    if [ "$MACHINE_FORMAT" != "fit" ]; then
        return
    fi

    info "Checking FIT image format."
    itb="$(temp_file)"
    vbutil_kernel --get-vmlinuz "${1:-$IMAGE}" --vmlinuz-out "$itb"
    if mkimage -l "$itb" | head -1 | grep -qs '^FIT description:'; then
        : # FIT image.
    else
        error "Depthcharge image not created from a FIT image." || :
        return 6
    fi
}

cmd_main() {
    if ! machine_is_supported; then
        error "Cannot verify images for unsupported machine '$MACHINE'."
    fi

    check_readable "$IMAGE"
    check_size "$IMAGE"
    check_depthcharge_image "$IMAGE"
    check_signature "$IMAGE"
    check_fit_format "$IMAGE"
}
