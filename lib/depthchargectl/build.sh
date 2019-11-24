# This file is sourced by depthchargectl.

usage() {
cat <<EOF
Usage:
 depthchargectl build [options] [kernel-version]

Build a depthcharge image for the running system.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -a, --all                  Rebuild images for all kernel versions.
EOF
}


# Parse options and arguments
# ---------------------------

set_kversion() {
    if [ -n "${KVERSION:-}" ]; then
        usage_error "Can't have kernel version multiple times" \
            "('$KVERSION', '${1:-}')."
    elif [ -n "${1:-}" ]; then
        info "Building for kernel version: $1"
        KVERSION="$1"
    fi
}

# Should return number of elemets to shift, never zero.
cmd_args() {
    case "$1" in
        # Options:
        -f|--force)         FORCE=yes;          return 1 ;;
        -a|--all)           ALL_IMAGES=yes;     return 1 ;;

        # End of options.
        -*) usage_error "Option '$1' not understood." ;;
        *)  set_kversion "$1"; return 1 ;;
    esac
}


# Set argument defaults
# ---------------------

cmd_defaults() {
    # Don't build all versions.
    : "${ALL_IMAGES:=no}"

    # Can be empty (for latest version), but needs to be set.
    : "${KVERSION:=}"

    # Giving --all is incompatible with giving a version.
    if [ "$ALL_IMAGES" = "yes" ] && [ -n "$KVERSION" ]; then
        usage_error "Can't specify both --all and a version ('$KVERSION')."
    fi

    readonly ALL_IMAGES KVERSION
}


# Write image to partition
# ------------------------

# Check if file is less than a maximum size.
size_check() {
    image="$1"
    max_size="${2:-${MAX_SIZE:-0}}"

    if [ "${max_size}" -gt 0 ]; then
        size="$(stat -c '%s' "$image")"
        if [ "$size" -gt "$max_size" ]; then
            return 1
        fi
    fi
}

build_image() {
    kversion="$1"
    output="$2"
    set --
    info "Trying to build a depthcharge image for version '$kversion'."

    # Vmlinuz is always mandatory.
    vmlinuz="$(kversion_vmlinuz "$kversion")" \
        || error "Version '$kversion' can't be resolved to a vmlinuz."
    if [ -z "$vmlinuz" ] || [ ! -r "$vmlinuz" ]; then
        error "Vmlinuz ('$vmlinuz') for '$kversion' is unusable."
    else
        set -- "--" "$vmlinuz"
    fi

    # Initramfs is optional if this succeeds but is empty.
    initramfs="$(kversion_initramfs "$kversion")" \
        || error "Version '$kversion' can't be resolved to an initramfs."
    if [ -n "$initramfs" ]; then
        if [ ! -r "$initramfs" ]; then
            error "Initramfs ('$initramfs') for '$kversion is unusable'."
        fi
        set -- "$@" "$initramfs"
    fi

    # Device trees are optional based on machine configuration.
    dtbs_path="$(kversion_dtbs_path "$kversion")" \
        || error "Version '$kversion' can't be resolved to a dtbs dir."
    if [ -n "$MACHINE_DTB_NAME" ]; then
        if [ -z "$dtbs_path" ]; then
            error "No dtbs exist, but this machine needs one."
        fi

        info "Searching '$dtbs_path' for '$MACHINE_DTB_NAME'."
        dtbs="$(find "$dtbs_path" -iname "$MACHINE_DTB_NAME")" \
            || error "Couldn't search for dtbs in '$dtbs_path'."

        if [ -z "$dtbs" ]; then
            error "No dtb file '$MACHINE_DTB_NAME' found in '$dtbs_path'."
        else
            IFS="$CUSTOM_IFS"
            set -- "$@" $dtbs
            IFS="$ORIG_IFS"
        fi
    fi

    cmdline="$CONFIG_CMDLINE"
    # Custom kernels might still be able to boot without an initramfs,
    # but we need to inject a root= parameter for that.
    if [ -z "$initramfs" ]; then
        if cmdline_has_root "$CONFIG_CMDLINE"; then
            info "No initramfs, but root is set in user configured cmdline."
        else
            info "No initramfs, trying to prepend root into cmdline."
            rootcmd="$(get_root_cmdline)" \
                || error "Couldn't figure out a root cmdline parameter."
            check_root_cmdline "$rootcmd" \
                || error "An initramfs is required for '$rootcmd'."

            # Prepend it so that user-given cmdline overrides it.
            info "Prepending '$rootcmd' to the kernel cmdline."
            cmdline="${rootcmd}${cmdline:+ }${cmdline:-}"
        fi
    fi

    # We need this for the firmware to tell us the booted partition.
    cmdline="kern_guid=%U${cmdline:+ }${cmdline:-}"
    if [ -n "$cmdline" ]; then
        set -- "--cmdline" "$cmdline" "$@"
    fi

    # Human readable description for the image.
    description="$(kversion_description "$kversion")" \
        || error "Version '$kversion' can't be resolved to a description."
    if [ -n "$description" ]; then
        set -- "--description" "$description" "$@"
    fi

    # If we are verbose, set mkdepthcharge to verbose too.
    if [ "$VERBOSE" = "yes" ]; then
        set -- "--verbose" "$@"
    fi

    # Try to keep the output reproducible. Initramfs date is bound to be
    # later than vmlinuz date, so prefer that if possible.
    if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
        SOURCE_DATE_EPOCH="$(
            stat -c "%Y" "$initramfs" || stat -c "%Y" "$vmlinuz" \
        )" || error "Couldn't determine a date from initramfs nor vmlinuz."
        export SOURCE_DATE_EPOCH
    fi

    # We can't just put compress into "$@" since we need to try
    # different values one by one, here.
    info "Building depthcharge image for kernel version '$kversion':"
    for compress in ${CONFIG_COMPRESS:-none}; do
        info "Trying with compression set to '$compress'."
        mkdepthcharge --output "$output" --compress "$compress" "$@" \
            || error "Failed to create depthcharge image."
        if size_check "$output" "$MACHINE_MAX_SIZE"; then
            break
        else
            warn "Image built with compression '$compress' is too big."
        fi
    done

    # This is redundant now, but here just to raise an error.
    info "Checking built image size against firmware limits."
    size_check "$output" "$MACHINE_MAX_SIZE" \
        || error "Depthcharge image '$output' is too big to boot."
}

cmd_main() {
    if [ "$ALL_IMAGES" = "yes" ]; then
        for kversion in $(kversions); do
            output="$(temp_file "depthcharge.img-$kversion")"
            build_image "$kversion" "$output" \
                || warn "Couldn't generate image for version '$kversion'."
            msg "built $output"
        done
        return
    fi

    kversion="${KVERSION:-$(kversions | head -1)}"
    output="$(temp_file "depthcharge.img-$kversion")"
    build_image "$kversion" "$output" \
        || error "Couldn't build image for version '$kversion'."
        msg "built $output"
}

