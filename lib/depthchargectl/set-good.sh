# This file is sourced by depthchargectl.

usage() {
cat <<EOF
Usage:
 depthchargectl set-good [options]

Set the current ChromeOS kernel partition as successfully booted.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
EOF
}


# Parse options and arguments
# ---------------------------

# Should return number of elemets to shift, never zero.
cmd_args() {
    case "$1" in
        # No options or arguments.
        -*) usage_error "Option '$1' not understood." ;;
        *)  usage_error "Argument '$1' not understood." ;;
    esac
}


# Set argument defaults
# ---------------------

cmd_defaults() {
    : # No options or arguments.
}


# Set partition as good
# ---------------------

cmd_main() {
    partuuid="$(get_kern_guid)" \
        || error "Couldn't figure out the currently booted partition."
    partdev="$(cgpt find -1 -u "$partuuid" 2>/dev/null)" \
        || error "No partition with PARTUUID='$partuuid' found."

    disk="$(disk_from_partdev "$partdev")"
    partno="$(partno_from_partdev "$partdev")"
    if [ ! -b "$disk" ]; then
        error "Currently booted disk '$disk' is not a valid block device."
    elif [ ! -w "$disk" ]; then
        error "Currently booted disk '$disk' is not writable."
    fi
    case "$partno" in
        *[!0-9]*) error "Parsed invalid partition no for '$partdev'." ;;
    esac

    typeguid="$(cgpt_ show -i "$partno" -t "$disk")"
    if [ "$typeguid" != "FE3A2A5D-4F32-41A7-B725-ACCC3285A309" ]; then
        error "Partition '$partdev' is not a ChromeOS kernel partition."
    fi

    info "Setting '$partdev' as the highest-priority bootable part."
    cgpt_ add -i "$partno" -T 1 -S 1 "$disk" \
        || error "Failed to set partition '$TARGET_PART' as bootable."
    cgpt_ prioritize -i "$partno" "$disk" \
        || error "Failed to prioritize partition '$TARGET_PART'."
}
