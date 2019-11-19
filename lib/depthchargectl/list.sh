#!/bin/sh
set -eu

usage() {
cat <<EOF
Usage:
 depthchargectl list [options]

List ChromeOS kernel partitions.

Options:
 -h, --help                 Show this help message.
 -v, --verbose              Print more detailed output.
EOF
}

. "lib/msg.sh"


# Parse options and arguments
# ---------------------------

while [ "$#" -gt 0 ]; do
    case "$1" in
        # Options:
        -h|--help)      usage;          exit 0 ;;
        -v|--verbose)   VERBOSE=yes;    shift 1 ;;

        # End of options.
        -*) usage_error "Option '$1' not understood." ;;
    esac
done
