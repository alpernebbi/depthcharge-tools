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
    partdev="$(cgpt_ find -1 -u "$partuuid" 2>/dev/null)" \
        || error "No partition with PARTUUID='$partuuid' found."

    depthchargectl target --allow-current "$partdev" >/dev/null \
        || error "Partition '$partdev' is not a usable partition."

    disk="$(disk_from_partdev "$partdev")"
    partno="$(partno_from_partdev "$partdev")"

    info "Setting '$partdev' as the highest-priority bootable part."
    cgpt_ add -i "$partno" -P 1 -T 1 -S 1 "$disk" \
        || error "Failed to set partition '$TARGET_PART' as bootable."
    cgpt_ prioritize -i "$partno" "$disk" \
        || error "Failed to prioritize partition '$TARGET_PART'."
}
