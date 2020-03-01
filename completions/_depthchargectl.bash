# vim: filetype=sh

_depthchargectl__file() {
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

_depthchargectl__disk() {
    COMPREPLY+=($(compgen -W "$(lsblk -o "PATH" -n -l)" -- "$cur"))
}

_depthchargectl__kernel() {
    if command -v _kernel_versions >/dev/null 2>/dev/null; then
        _kernel_versions
    fi
}

_depthchargectl() {
    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    local global_opts=(-h --help --version -v --verbose)
    local cmds=(build check partitions rm set-good target write)

    local cmd
    for cmd in "${COMP_WORDS[@]}"; do
        case "$cmd" in
            build)      _depthchargectl_build; break ;;
            check)      _depthchargectl_check; break ;;
            partitions) _depthchargectl_partitions; break ;;
            rm)         _depthchargectl_rm; break ;;
            set-good)   _depthchargectl_set-good; break ;;
            target)     _depthchargectl_target; break ;;
            write)      _depthchargectl_write; break ;;
            *) cmd="" ;;
        esac
    done

    if [ -z "$cmd" ]; then
        COMPREPLY+=($(compgen -W "${cmds[*]}" -- "$cur"))
        COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
    fi
}

_depthchargectl_build() {
    local opts=(-f --force -a --all --reproducible)
    _depthchargectl__kernel
    COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
}

_depthchargectl_check() {
    _depthchargectl__file
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
}

_depthchargectl_partitions() {
    local opts=(-a --all-disks -n --noheadings -o --output)
    local outputs=(S SUCCESSFUL T TRIES P PRIORITY SIZE DEVICE)
    case "$prev" in
        -o|--output)
            compopt -o nospace
            case "$cur" in
                *,) COMPREPLY+=($(compgen -W "${outputs[*]}" -P "$cur" -- "")) ;;
                *,*) COMPREPLY+=($(compgen -W "${outputs[*]}" -P "${cur%,*}," -- "${cur##*,}")) ;;
                *) COMPREPLY+=($(compgen -W "${outputs[*]}" -- "$cur")) ;;
            esac
            ;;
        *)
            _depthchargectl__disk
            COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
            COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
            ;;
    esac
}

_depthchargectl_rm() {
    local opts=(-f --force)
    _depthchargectl__file
    COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
}

_depthchargectl_set-good() {
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
}

_depthchargectl_target() {
    local opts=(-s --min-size --allow-current)
    local sizes=(16777216 33554432)
    case "$prev" in
        -s|--min-size)
            COMPREPLY+=($(compgen -W "${sizes[*]}" -- "$cur"))
            ;;
        *)
            _depthchargectl__disk
            COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
            COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
            ;;
    esac
}

_depthchargectl_write() {
    local opts=(-f --force -t --target --no-prioritize --allow-current)
    case "$prev" in
        -t|--target)
            _depthchargectl__disk
            ;;
        *)
            _depthchargectl__kernel
            _depthchargectl__file
            COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
            COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
            ;;
    esac
}

complete -F _depthchargectl depthchargectl
