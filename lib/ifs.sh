# Whitespace
# ----------

ORIG_IFS="$IFS"
CUSTOM_IFS="$(printf "\n\t")"
NEWLINE="${CUSTOM_IFS%?}"
TAB="${CUSTOM_IFS#?}"
COMMA=","

has_newline() {
    case "$1" in
        *"$NEWLINE"*) return 0 ;;
        *) return 1 ;;
    esac
}

readonly ORIG_IFS CUSTOM_IFS NEWLINE TAB
