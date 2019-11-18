# Functions to make printing output easier.
msg() {
    if [ "$#" -gt 0 ]; then
        echo "$0:" "$@"
    fi
}

info() {
    if [ "$VERBOSE" = yes ]; then
        msg "$@"
    fi
}

warn() {
    msg "warning:" "$@" >&2
}

error() {
    msg "error:" "$@" >&2
    exit 1
}

usage_error() {
    msg "error:" "$@" "\n" >&2
    usage >&2
    exit 1
}

