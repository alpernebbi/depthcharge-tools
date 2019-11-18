# Printing output
# ---------------

msg() {
    if [ "$#" -gt 0 ]; then
        printf "%s " "${PROG:-${0##*/}}:" "$@"
    fi
    printf "\n"
}

info() {
    if [ "${VERBOSE:-no}" = yes ] && [ "$#" -gt 0 ]; then
        msg "info:" "$@"
    fi
} >&2

warn() {
    if [ "${QUIET:-no}" != yes ] && [ "$#" -gt 0 ]; then
        msg "warning:" "$@"
    fi
} >&2

error() {
    if [ "${SILENT:-no}" != yes ] && [ "$#" -gt 0 ]; then
        msg "error:" "$@"
    fi
    return 1
} >&2

usage_error() {
    if [ "${SILENT:-no}" != yes ]; then
        msg "usage error:" "$@"
        msg
        if command -v usage >/dev/null; then
            usage
        else
            printf "%s\n" "${PROG:-${0##*/}} has no usage information."
        fi
    fi
    exit 1
} >&2
