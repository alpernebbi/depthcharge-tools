# Handling temporary files
# ------------------------

# This is a subfolder in the original TMPDIR if that's given.
TMPDIR="$(mktemp -td "${PROG:-${0##*/}}.XXXXXXXX")"
trap 'rm -rf "${TMPDIR}"' EXIT
export TMPDIR

temp_file() {
    mktemp -t "${1:-zz}-XXXXXXXX"
}

temp_dir() {
    mktemp -t -d "${1:-zz}-XXXXXXXX"
}

temp_copy() {
    temp="$(temp_file "$(basename "$1")")"
    cp -T "$1" "$temp"
    echo "$temp"
    unset temp
}
