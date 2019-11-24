# Kernel Versions and Files
# -------------------------

# Print available kernel versions, in descending priority.
kversions() {
    # Debian has a command for this.
    if command -v linux-version >/dev/null; then
        linux-version list | linux-version sort --reverse
    fi
}

# The path to the vmlinuz for a kernel version.
kversion_vmlinuz() {
    printf "/boot/vmlinuz-%s\n" "$1"
}

# The path to the initramfs image for a kernel version.
# Can be empty if the depthcharge image should be built without one.
kversion_initramfs() {
    printf "/boot/initrd.img-%s\n" "$1"
}

# The directory containing the device-tree files for a kernel version.
# Can be empty if the architecture has no such files.
kversion_dtbs_path() {
    dtbs_path="$(printf "/usr/lib/linux-image-%s\n" "$1")"
    if [ -d "$dtbs_path" ]; then
        printf "%s\n" "$dtbs_path"
    fi
}

# Description for a kernel version.
kversion_description() {
    if [ -f /etc/os-release ]; then
        name="$(sed -n -e 's/^NAME="\(.*\)"/\1/1p' /etc/os-release)"
        printf "%s with kernel %s" "$name" "$1"
    else
        printf "Kernel %s" "$1"
    fi
}


# Kernel Cmdline Paramteters
# --------------------------

# ChromeOS firmware injects one of these values into the cmdline based
# on which boot mechanism is used. A 'secure' argument allows us to
# select for devices where a cros partition is absolutely necessary.
is_cros_machine() {
    case "$(cat "/proc/cmdline")" in
        *cros_secure*)
            return 0
            ;;
        *cros_efi*|*cros_legacy*)
            [ "$1" = "secure" ] && return 1
            return 0
            ;;
    esac
    return 1
}

# Returns the PARTUUID of the ChromeOS kernel partition we booted from.
# mkdepthcharge puts "kern_guid=%U" in the cmdline, and the firmware
# should have replaced it with this partuuid.
get_kern_guid() {
    guid="$(sed -n -e 's/.*kern_guid=\([^ ]*\).*/\1/p' "/proc/cmdline")"
    if [ -n "$guid" ] && [ "$guid" != "%U" ]; then
        echo "$guid"
    else
        return 1
    fi
}

# Tries to validate the root=* kernel cmdline parameter.
# See init/do_mounts.c in Linux tree.
check_root_cmdline() {
    d="[0-9]"
    x="[0-9a-f]"
    a="[0-9a-z]"
    uuid="$x{8}-$x{4}-$x{4}-$x{4}-$x{12}"
    ntsig="$x{8}-$x{2}"

    printf "%s\n" "$1" | grep -E -q -x \
        -e "root=$x{4}" \
        -e "root=/dev/nfs" \
        -e "root=/dev/$a+" \
        -e "root=/dev/$a+$d+" \
        -e "root=/dev/$a+p$d+" \
        -e "root=PARTUUID=($uuid|$ntsig)" \
        -e "root=PARTUUID=($uuid|$ntsig)/PARTNROFF=$d+" \
        -e "root=$d+:$d+" \
        -e "root=PARTLABEL=.*"
}

# Gets a kernel cmdline for the root set in /etc/fstab.
get_root_cmdline() {
    rootdev="$(
        findmnt --fstab -M "/" -n -o SOURCE \
            | sed -e 's/\="\(.*\)"$/\=\1/' -e 's/ /\\x20/g' \
    )"

    if [ -n "$rootdev" ]; then
        echo "root=$rootdev"
    else
        return 1
    fi
}

# Check if a given cmdline already sets root.
cmdline_has_root() {
    case "$1" in
        *root=*) return 0 ;;
        *) return 1 ;;
    esac
}
