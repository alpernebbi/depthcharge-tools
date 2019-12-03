# This file is sourced by depthchargectl.
PROG="depthchargectl build"
usage() {
cat <<EOF
Usage:
 depthchargectl build [options] [kernel-version]

Build a depthcharge image for the running system.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -a, --all                  Rebuild images for all kernel versions.
 -f, --force                Rebuild images even if unnecessary.
     --reproducible         Try to build a reproducible image.
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
        --reproducible)     REPRODUCIBLE=yes;   return 1 ;;

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

    # Embed current date into the image.
    : "${REPRODUCIBLE:=${SOURCE_DATE_EPOCH:+yes}}"
    : "${REPRODUCIBLE:=no}"

    # Don't rebuild images unless inputs have changed.
    : "${FORCE:=no}"

    readonly ALL_IMAGES KVERSION REPRODUCIBLE FORCE
}


# Write image to partition
# ------------------------

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
            IFS="${NEWLINE}${TAB}"
            set -- "$@" $dtbs
            IFS="$ORIG_IFS"
        fi
    fi

    cmdline="$CONFIG_CMDLINE"
    # Custom kernels might still be able to boot without an initramfs,
    # but we need to inject a root= parameter for that.
    if cmdline_has_root "$CONFIG_CMDLINE"; then
        info "Using root as set in user configured cmdline."
    else
        info "Trying to prepend root into cmdline."
        rootcmd="$(get_root_cmdline)" \
            || error "Couldn't figure out a root cmdline parameter."
        if [ -z "$initramfs" ] && ! check_root_cmdline "$rootcmd"; then
            error "An initramfs is required for '$rootcmd'."
        fi

        # Prepend it so that user-given cmdline overrides it.
        info "Prepending '$rootcmd' to the kernel cmdline."
        cmdline="${rootcmd}${cmdline:+ }${cmdline:-}"
    fi
    if [ -n "$cmdline" ]; then
        set -- "--cmdline" "$cmdline" "$@"
    fi

    # Human readable description for the image.
    description="$(kversion_description "$kversion")" \
        || error "Version '$kversion' can't be resolved to a description."
    if [ -n "$description" ]; then
        set -- "--description" "$description" "$@"
    fi

    # Signing keys to use.
    set -- "--keyblock" "$CONFIG_VBOOT_KEYBLOCK" "$@"
    set -- "--signprivate" "$CONFIG_VBOOT_SIGNPRIVATE" "$@"

    # If we are verbose, set mkdepthcharge to verbose too.
    if [ "$VERBOSE" = "yes" ]; then
        set -- "--verbose" "$@"
    fi

    # Try to keep the output reproducible. Initramfs date is bound to be
    # later than vmlinuz date, so prefer that if possible.
    if [ "${REPRODUCIBLE}" = yes ] && [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
        SOURCE_DATE_EPOCH="$(
            stat -c "%Y" "$initramfs" || stat -c "%Y" "$vmlinuz" \
        )" || error "Couldn't determine a date from initramfs nor vmlinuz."
        export SOURCE_DATE_EPOCH
    fi

    # Keep information about input files and configuration.
    new_inputs="$(temp_file "${kversion}.img.inputs")"
    (
        printf "# Software versions:\n"
        printf "%s: %s\n" \
            Depthchargectl-Version "$(depthchargectl --version)" \
            Mkdepthcharge-Version "$(mkdepthcharge --version)"
        printf "\n"

        printf "# Machine info:\n"
        printf "%s: %s\n" \
            Machine "$MACHINE" \
            DTB-Name "$MACHINE_DTB_NAME" \
            Max-Size "$MACHINE_MAX_SIZE"
        printf "\n"

        printf "# Image Configuration:\n"
        printf "%s: %s\n" \
            Kernel-Version "$kversion" \
            Kernel-Cmdline "$cmdline" \
            Kernel-Compress "${CONFIG_COMPRESS:-none}" \
            Kernel-Description "$description" \
            Source-Date-Epoch "${SOURCE_DATE_EPOCH:-unset}"
        printf "\n"

        printf "# Image Inputs:\n"
        printf "%s: %s\n" \
            Vmlinuz "$vmlinuz" \
            Initramfs "${initramfs:-}"
        IFS="${NEWLINE}${TAB}"
        printf "DTB: %s\n" $dtbs
        IFS="${ORIG_IFS}"
        printf "\n"

        printf "# Signing Keys:\n"
        printf "%s: %s\n" \
            Vboot-Keyblock "$CONFIG_VBOOT_KEYBLOCK" \
            Vboot-Public-Key "$CONFIG_VBOOT_SIGNPUBKEY" \
            Vboot-Private-Key "$CONFIG_VBOOT_SIGNPRIVATE"
        printf "\n"

        printf "# SHA256 Checksums:\n"
        IFS="${NEWLINE}${TAB}"
        sha256sum "$vmlinuz" $initramfs $dtbs \
            "$CONFIG_VBOOT_KEYBLOCK" \
            "$CONFIG_VBOOT_SIGNPUBKEY" \
            "$CONFIG_VBOOT_SIGNPRIVATE"
        IFS="${ORIG_IFS}"
    ) >"$new_inputs"

    if [ -r "${output}" ] && [ -r "${output}.inputs" ]; then
        if diff "${output}.inputs" "$new_inputs" >/dev/null; then
            info "Inputs are the same with those of existing image," \
                "no need to rebuild the image."
            msg "Cached image valid for kernel version '$kversion'."
            if [ "${FORCE:-no}" = no ]; then
                return 0
            else
                info "Rebuilding anyway."
                forced_rebuild=yes
            fi
        fi
    fi

    # Build in a temporary location so we do not overwrite existing
    # images with an unbootable image.
    new_img="$(temp_file "${kversion}.img")"

    # We can't just put compress into "$@" since we need to try
    # different values one by one, here.
    info "Building depthcharge image for kernel version '$kversion':"
    for compress in ${CONFIG_COMPRESS:-none}; do
        info "Trying with compression set to '$compress'."
        mkdepthcharge --output "$new_img" --compress "$compress" "$@" \
            || error "Failed to create depthcharge image."

        if depthchargectl check "$new_img" >/dev/null 2>/dev/null; then
            image_ok=yes
            break
        elif [ "$?" -eq 3 ]; then
            image_ok=too_big
            warn "Image with compression '$compress' is not bootable," \
                "will try a better one if possible."
        else
            image_ok=no
            break
        fi
    done

    # If we force-rebuilt the image, and we should've been reproducible,
    # check if it changed.
    if [ "$REPRODUCIBLE" = yes ] && [ "${forced_rebuild:-no}" = "yes" ]; then
        if ! diff "${output}" "${new_img}" >/dev/null; then
            warn "Force-rebuilding image changed it in reproducible mode." \
                "This is most likely a bug."
        fi
    fi

    if [ "${image_ok:-no}" = "yes" ]; then
        info "Copying newly built image and info to output."
        rm -f "${output}.inputs"
        cp -f "$new_img" "$output"
        cp -f "$new_inputs" "${output}.inputs"
        msg "Built image for kernel version '$kversion'."
        return 0

    elif [ "${image_ok:-no}" = "no" ]; then
        error "Couldn't build a bootable image for this machine." || :
        return 2

    elif [ "${image_ok:-no}" = "too_big" ] && [ -n "$initramfs" ]; then
        warn "The initramfs might be too big for this machine."
        warn "Usually this can be resolved by including less modules in" \
             "the initramfs and/or compressing it with a better algorithm."
        warn "Please check your distro's documentation for how to do this."
        error "Couldn't build a small enough image for this machine." || :
        return 3

    elif [ "${image_ok:-no}" = "too_big" ]; then
        error "Couldn't build a small enough image for this machine." || :
        return 4
    fi
}

cmd_main() {
    if ! machine_is_supported; then
        error "Cannot build images for unsupported machine '$MACHINE'."
    fi

    if [ "$ALL_IMAGES" = "yes" ]; then
        set -- $(kversions)
    elif [ -n "${KVERSION:-}" ]; then
        set -- "$KVERSION"
    else
        set -- "$(kversions | head -1)"
    fi

    mkdir -p "$IMAGES_DIR"

    for kversion in "$@"; do
        image="${IMAGES_DIR}/${kversion}.img"
        build_image "$kversion" "$image"
        printf "%s\n" "$image"
    done
}

