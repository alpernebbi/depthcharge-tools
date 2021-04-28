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
        -h --help -V --version -v --verbose
        -d --vmlinuz -i --initramfs -b --dtbs
        -o --output --tmpdir -A --arch --format
        -C --compress -n --name
        -c --cmdline --no-kern-guid --bootloader
        --keydir --keyblock --signprivate --signpubkey
    )

    case "$prev" in
        -d|--vmlinuz)   _mkdepthcharge__file ;;
        -i|--initramfs) _mkdepthcharge__file ;;
        -b|--dtbs)      _mkdepthcharge__file ;;
        -o|--output)    _mkdepthcharge__file ;;
        -A|--arch)      COMPREPLY+=($(compgen -W "arm arm64 aarch64 x86 x86_64 amd64" -- "$cur")) ;;
        --format)       COMPREPLY+=($(compgen -W "fit zimage" -- "$cur")) ;;
        -C|--compress)  COMPREPLY+=($(compgen -W "none lz4 lzma" -- "$cur")) ;;
        -n|--name)
            local name="$(. /etc/os-release; echo "$NAME")"
            COMPREPLY+=($(compgen -W "$name" -- "$cur"))
            ;;
        -c|--cmdline)
            cmdline="$(cat /proc/cmdline | sed -e 's/\(cros_secure\|kern_guid\)[^ ]* //g')"
            COMPREPLY+=($(compgen -W "$cmdline" -- "$cur"))
            ;;
        --tmpdir)       _mkdepthcharge__file ;;
        --bootloader)   _mkdepthcharge__file ;;
        --keydir)       _mkdepthcharge__file ;;
        --keyblock)     _mkdepthcharge__file ;;
        --signprivate)  _mkdepthcharge__file ;;
        --signpubkey)   _mkdepthcharge__file ;;
        --)             _mkdepthcharge__file ;;
        *)
            COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
            _mkdepthcharge__file
            ;;
    esac
}

complete -F _mkdepthcharge mkdepthcharge
