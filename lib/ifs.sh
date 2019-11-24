# Whitespace
# ----------

ORIG_IFS="$IFS"
NEWLINE="$(printf "\n\t")"
NEWLINE="${NEWLINE%?}"
TAB="$(printf "\t")"

has_newline() {
    case "$1" in
        *"$NEWLINE"*) return 0 ;;
        *) return 1 ;;
    esac
}

readonly ORIG_IFS NEWLINE TAB
