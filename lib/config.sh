# Parsing configuration files
# ---------------------------

# Finds values for a key, among input lines of "<key>: <values>".
parse_field() {
    output="$(sed -n -e "
        /^$1: / { s/^$1: //1; h }
        \$ {x;p}
    ")"

    if [ -n "$output" ]; then
        printf "%s\n" "$output"
    else
        return 1
    fi
}

# Like parse_config, but only considers blocks of lines whose first line
# is a certain "Machine: <machine>".
parse_machine_field() {
    output="$(sed -n -e "
        /^Machine: $1\$/,/^\$/ {
            /^$2: / { s/^$2: //1; h }
        }
        \$ {x;p}
    ")"

    if [ -n "$output" ]; then
        printf "%s\n" "$output"
    else
        return 1
    fi
}

# Checks if a block with "Machine: <machine>" exists in the input.
parse_machine_exists() {
    grep -qs "^Machine: $1\$"
}

# Read files but ignore commented lines. Insert newlines between files
# since parse_db uses an empty line as a block delimiter and two files
# could accidentally merge into one block otherwise.
read_files() {
    for f in "$@"; do
        grep -sv '^#' "$f" && echo || :
    done
}

