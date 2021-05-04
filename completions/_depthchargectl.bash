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

_depthchargectl__boards() {
    # later
    local script="import re"
    script="$script;from depthcharge_tools import boards_ini"
    script="$script;boards = re.findall(\"codename = (.+)\", boards_ini)"
    script="$script;print(*sorted(boards))"
    COMPREPLY+=($(compgen -W "$(python3 -c "$script")" -- "$cur"))
}

_depthchargectl() {
    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    local global_opts=(-h --help -V --version -v --verbose --tmpdir)
    local config_opts=(
        --config --board --images-dir
        --vboot-keyblock --vboot-public-key --vboot-private-key
        --kernel-cmdline --ignore-initramfs
    )
    local cmds=(bless build config check list remove target write)

    case "$prev" in
        --tmpdir) _depthchargectl__file; return ;;
        --config) _depthchargectl__file; return ;;
        --board) _depthchargectl__boards; return ;;
        --images-dir) _depthchargectl__file; return ;;
        --vboot-keyblock) _depthchargectl__file; return ;;
        --vboot-public-key) _depthchargectl__file; return ;;
        --vboot-private-key) _depthchargectl__file; return ;;
        --kernel-cmdline)
            cmdline="$(cat /proc/cmdline | sed -e 's/\(cros_secure\|kern_guid\)[^ ]* //g')"
            COMPREPLY+=($(compgen -W "$cmdline" -- "$cur"))
            return
            ;;
        --ignore-initramfs) : ;;
        --) ;;
        *) ;;
    esac

    local cmd
    for cmd in "${COMP_WORDS[@]}"; do
        case "$cmd" in
            bless)      _depthchargectl_bless; break ;;
            build)      _depthchargectl_build; break ;;
            config)     _depthchargectl_config; break ;;
            check)      _depthchargectl_check; break ;;
            list)       _depthchargectl_list; break ;;
            remove)     _depthchargectl_remove; break ;;
            target)     _depthchargectl_target; break ;;
            write)      _depthchargectl_write; break ;;
            *) cmd="" ;;
        esac
    done

    if [ -z "$cmd" ]; then
        COMPREPLY+=($(compgen -W "${cmds[*]}" -- "$cur"))
        COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
        COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
    fi
}

_depthchargectl_bless() {
    local opts=(--bad --oneshot -i --partno)
    case "$prev" in
        -i|--partno) return ;;
        *) _depthchargectl__disk ;;
    esac
    COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
}

_depthchargectl_build() {
    local opts=(
        --description --root --compress --timestamp -o --output
        --kernel-release --kernel --initramfs --fdtdir --dtbs
)
    case "$prev" in
        --description)
            local name="$(. /etc/os-release; echo "$NAME")"
            COMPREPLY+=($(compgen -W "$name" -- "$cur"))
            return
            ;;
        --root)
            local root="$(findmnt --fstab -n -o SOURCE "/")"
            COMPREPLY+=($(compgen -W "$root" -- "$cur"))
            _depthchargectl__disk
            return
            ;;
        --compress)
            local compress=(none lz4 lzma)
            COMPREPLY+=($(compgen -W "${compress[*]}" -- "$cur"))
            return
            ;;
        --timestamp)
            COMPREPLY+=($(compgen -W "$(date "+%s")" -- "$cur"))
            return
            ;;
        -o|--output) _depthchargectl__file; return ;;
        --kernel-release) _depthchargectl__kernel; return ;;
        --kernel) _depthchargectl__file; return ;;
        --initramfs) _depthchargectl__file; return ;;
        --fdtdir) _depthchargectl__file; return ;;
        --dtbs) _depthchargectl__file; return ;;
        *) _depthchargectl__kernel;;
    esac
    COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
}

_depthchargectl_config() {
    local opts=(--section --default)
    case "$prev" in
        --section) return ;;
        --default) return ;;
        *) ;;
    esac
    COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
}

_depthchargectl_check() {
    _depthchargectl__file
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
}

_depthchargectl_list() {
    local opts=(-a --all-disks -n --noheadings -o --output)
    local outputs=(A ATTRIBUTE S SUCCESSFUL T TRIES P PRIORITY PATH DISK DISKPATH PARTNO SIZE)
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
            COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
            ;;
    esac
}

_depthchargectl_remove() {
    local opts=(-f --force)
    _depthchargectl__file
    _depthchargectl__kernel
    COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
    COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
}

_depthchargectl_target() {
    local opts=(-s --min-size --allow-current)
    local sizes=(8388608 16777216 33554432 67108864 134217728 268435456 536870912)
    case "$prev" in
        -s|--min-size)
            COMPREPLY+=($(compgen -W "${sizes[*]}" -- "$cur"))
            ;;
        *)
            _depthchargectl__disk
            COMPREPLY+=($(compgen -W "${opts[*]}" -- "$cur"))
            COMPREPLY+=($(compgen -W "${global_opts[*]}" -- "$cur"))
            COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
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
            COMPREPLY+=($(compgen -W "${config_opts[*]}" -- "$cur"))
            ;;
    esac
}

complete -F _depthchargectl depthchargectl
