# This file is sourced by depthchargectl.

usage() {
cat <<EOF
Usage:
 depthchargectl rm [options] [kernel-version | image]

Remove images for a version and disable partitions containing them.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -f, --force                Allow removing the current partition.
EOF
}


# Parse options and arguments
# ---------------------------

set_kversion() {
    if [ -n "${KVERSION:-}" ]; then
        usage_error "Can't have kernel version multiple times" \
            "('$KVERSION', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        info "Using kernel version: $1"
        KVERSION="$1"
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

set_source() {
    if [ -n "${KVERSION:-}" ] || [ -n "${IMAGE:-}" ]; then
        usage_error "Can't have multiple inputs " \
            "('${KVERSION:-$IMAGE}', '${1:-}'."
    elif [ -n "${1:-}" ]; then
        # This can be run after the kernel is uninstalled, where the
        # version would no longer be valid, so don't check for that.
        if [ -f "${IMAGES_DIR}/${1}.img" ]; then
            set_kversion "$1"
        else
            set_image "$1"
        fi
    fi
}

# Should return number of elemets to shift, never zero.
cmd_args() {
    case "$1" in
        -f|--force)         FORCE=yes;          return 1 ;;

        # End of options.
        -*) usage_error "Option '$1' not understood." ;;
        *)  set_source "$1"; return 1 ;;
    esac
}


# Set argument defaults
# ---------------------

cmd_defaults() {
    # By default, don't delete anything.
    : "${KVERSION:=}"

    if [ -n "${KVERSION:-}" ]; then
        : "${IMAGE:=${IMAGES_DIR}/${KVERSION}.img}"
    else
        : "${IMAGE:=}"
    fi

    if [ -z "${IMAGE:-}" ]; then
        usage_error "Either a kernel-version or an image is necessary."
    fi

    # Don't remove the current partition.
    : "${FORCE:=no}"

    readonly KVERSION IMAGE
}


# Write image to partition
# ------------------------

cmd_main() {
    if [ ! -r "$IMAGE" ]; then
        if [ -n "${KVERSION}" ]; then
            error "No image found for kernel-version '$KVERSION'."
        else
            error "Image '$IMAGE' not found or not readable."
        fi
    fi

    if [ "${FORCE:-no}" = "yes" ]; then
        set -- "--allow-current"
    fi

    if [ "${VERBOSE:-no}" = "yes" ]; then
        set -- "$@" "--verbose"
    fi

    info "Searching for ChromeOS kernels containing '$IMAGE'."
    for partdev in $(cgpt_ find -t kernel -M "$IMAGE"); do
        info "Checking partition '$partdev'."
        # This checks currently booted partition among other things.
        if depthchargectl target "$@" "$partdev" >/dev/null; then
            disk="$(disk_from_partdev "$partdev")"
            partno="$(partno_from_partdev "$partdev")"

            info "Deactivating '$partdev'."
            cgpt_ add -T 0 -P 0 -S 0 -i "$partno" "$disk"
            printf "%s\n" "$partdev"
        else
            warn "Couldn't deactivate '$partdev', will not delete image."
            remove=no
        fi
    done

    case "$IMAGE" in
        "${IMAGES_DIR}/${KVERSION}.img") : "${remove:=yes}";;
        *) remove=no ;;
    esac

    if [ "${remove:-no}" = "yes" ]; then
        info "Image '$IMAGE' is in images dir, deleting."
        rm -f "${IMAGE}" "${IMAGE}.inputs"
    else
        info "Not deleting image '$IMAGE'."
    fi
}
