# This file is sourced by depthchargectl.

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

check_signature() {
    info "Checking image signatures."
    if ! futility vbutil_kernel >/dev/null \
            --signpubkey "$CONFIG_VBOOT_SIGNPUBKEY" \
            --verify "${1:-$IMAGE}"; then
        error "Depthcharge image cannot be verified by vbutil_kernel." || :
        return 4
    fi
}

cmd_main() {
    if ! machine_is_supported; then
        error "Cannot verify images for unsupported machine '$MACHINE'."
    fi

    check_readable
    check_size
    check_signature
}
