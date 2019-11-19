#!/bin/sh
set -eu

usage() {
cat <<EOF
Usage:
 depthchargectl list [options] [disk ...]

List ChromeOS kernel partitions.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print info messages to stderr.
 -n, --noheadings           Don't print column headings.
 -o, --output COLUMNS       Comma separated list of columns to output.

Supported columns:
    SUCCESSFUL (S), TRIES (T), PRIORITY (P), DEVICE
EOF
}

. "lib/msg.sh"
. "lib/cgpt.sh"
. "lib/ifs.sh"

# Supporting a comma separated list of columns needs a comma in IFS.
# We'll need to separate the table on spaces, so keep original IFS.
IFS="${IFS}${COMMA}"
readonly IFS

# Parse options and arguments
# ---------------------------

add_column() {
    if has_newline "${1:-}"; then
        error "Newlines not allowed in column names."
    fi

    # Check if in supported columns
    case "${1:-}" in
        # Recursively add columns if -o a,b,c given.
        *,*) for c in $1; do add_column "$c"; done; return ;;
        S|SUCCESSFUL) : ;;
        T|TRIES) : ;;
        P|PRIORITY) : ;;
        DEVICE) : ;;
        '') return ;;
        *) usage_error "Unsupported output column '$1'." ;;
    esac

    info "Adding column: $1"
    COLUMNS="${COLUMNS:-}${COLUMNS:+,}${1}"
}

add_disk() {
    if [ -n "${1:-}" ]; then
        info "Searching disk: $1"
        DISKS="${DISKS:-}${DISKS:+,}${1}"
    fi
}

# Check verbose options before printing anything.
for arg in "$@"; do
    case "${arg:-}" in
        -v|--verbose) VERBOSE=yes ;;
        --) break ;;
    esac
done

while [ "$#" -gt 0 ]; do
    case "$1" in
        # Options:
        -h|--help)          usage;              exit 0 ;;
        -v|--verbose)       VERBOSE=yes;        shift 1 ;;
        -n|--noheadings)    HEADINGS=no;        shift 1 ;;
        -o|--output)        add_column "$2";    shift 2 ;;

        # End of options.
        -*) usage_error "Option '$1' not understood." ;;
        *)  add_disk "$1"; shift ;;
    esac
done


# Set argument defaults
# ---------------------

# Verbosity options.
: "${VERBOSE:=no}"
: "${QUIET:=no}"
: "${SILENT:=no}"

# Output all columns by default.
: "${COLUMNS:=SUCCESSFUL,PRIORITY,TRIES,DEVICE}"

# Add heading by default.
: "${HEADINGS:=yes}"

# Can be empty (for all disks) but needs to be set.
: "${DISKS:=}"

readonly VERBOSE QUIET SILENT
readonly COLUMNS HEADINGS
readonly DISKS


# Print partition table
# ---------------------

set -- $COLUMNS

if [ "$HEADINGS" = "yes" ]; then
    info "Printing headings:"
    for c in "$@"; do
        case "$c" in
            S|SUCCESSFUL)   printf "%-2s " S ;;
            T|TRIES)        printf "%-2s " T ;;
            P|PRIORITY)     printf "%-2s " P ;;
            DEVICE)         printf "%-20s " DEVICE ;;
        esac
    done
    printf "\n"
fi

info "Printing table:"
(
    set -- $DISKS
    depthcharge_parts_table "$@"
) | {
    while read -r S P T DEVICE; do
        for c in "$@"; do
            case "$c" in
                S|SUCCESSFUL)   printf "%-2s "  "$S" ;;
                T|TRIES)        printf "%-2s "  "$T" ;;
                P|PRIORITY)     printf "%-2s "  "$P" ;;
                DEVICE)         printf "%-20s " "$DEVICE" ;;
            esac
        done
        printf "\n"
    done
}
