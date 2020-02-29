# vim: filetype=sh

_mkdepthcharge__file() {
    COMPREPLY+=($(compgen -f -- "$cur"))
    compopt -o filenames
    if [ "${#COMPREPLY[@]}" -eq 1 ]; then
        if [ -d "${COMPREPLY[0]}" ]; then
            compopt -o nospace
            COMPREPLY=("${COMPREPLY[0]}/")
        elif [ -f "${COMPREPLY[0]}" ]; then
            compopt +o nospace
        fi
    fi
}

_mkdepthcharge() {
    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    local opts=(
        -h --help --version -v --verbose
        -o --output -A --arch --format
        -C --compress -n --name
        -c --cmdline --no-kern-guid --bootloader
        --devkeys --keyblock --signprivate
    )

    case "$prev" in
        -o|--output)    _mkdepthcharge__file ;;
        -A|--arch)      COMPREPLY+=($(compgen -W "arm arm64 aarch64 x86 x86_64 amd64" -- "$cur")) ;;
        --format)       COMPREPLY+=($(compgen -W "fit zimage" -- "$cur")) ;;
        -C|--compress)  COMPREPLY+=($(compgen -W "none lz4 lzma" -- "$cur")) ;;
        -n|--name) : ;;
        -c|--cmdline)
            cmdline="$(cat /proc/cmdline | sed -e 's/\(cros_secure\|kern_guid\)[^ ]* //g')"
            COMPREPLY+=($(compgen -W "$cmdline" -- "$cur"))
            ;;
        --bootloader)   _mkdepthcharge__file ;;
        --devkeys)      _mkdepthcharge__file ;;
        --keyblock)     _mkdepthcharge__file ;;
        --signprivate)  _mkdepthcharge__file ;;
        --)             _mkdepthcharge__file ;;
        *)
            COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
            _mkdepthcharge__file
            ;;
    esac
}

complete -F _mkdepthcharge mkdepthcharge
