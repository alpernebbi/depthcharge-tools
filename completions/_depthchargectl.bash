# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools depthchargectl bash completions
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

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
} 2>/dev/null

_depthchargectl__timestamp() {
    local timestamp="$(date "+%s")"
    COMPREPLY+=($(compgen -W "$timestamp" -- "$cur"))
} 2>/dev/null

_depthchargectl__disk() {
    local disks="$(lsblk -o "PATH" -n -l)"
    COMPREPLY+=($(compgen -W "$disks" -- "$cur"))
} 2>/dev/null

_depthchargectl__root() {
    local root="$(findmnt --fstab -n -o SOURCE "/")"
    COMPREPLY+=($(compgen -W "$root" -- "$cur"))
} 2>/dev/null

_depthchargectl__boot() {
    local boot="$(findmnt --fstab -n -o SOURCE "/boot")"
    COMPREPLY+=($(compgen -W "$boot" -- "$cur"))
} 2>/dev/null

_depthchargectl__cmdline() {
    local cmdline="$(cat /proc/cmdline | sed -e 's/\(cros_secure\|kern_guid\)[^ ]* //g')"
    COMPREPLY+=($(compgen -W "$cmdline" -- "$cur"))
} 2>/dev/null

_depthchargectl__kernel() {
    if command -v _kernel_versions >/dev/null 2>/dev/null; then
        _kernel_versions
    else
        local script="from depthcharge_tools.utils.platform import installed_kernels"
        "$script;kernels = (k.release for k in installed_kernels());"
        "$script;print(*sorted(filter(None, kernels)));"
        COMPREPLY+=($(compgen -W "$(python3 -c "$script")" -- "$cur"))
    fi
} 2>/dev/null

_depthchargectl__boards() {
    # later
    local script="import re"
    script="$script;from depthcharge_tools import boards_ini"
    script="$script;boards = re.findall(\"codename = (.+)\", boards_ini)"
    script="$script;print(*sorted(boards))"
    COMPREPLY+=($(compgen -W "$(python3 -c "$script")" -- "$cur"))
} 2>/dev/null

_depthchargectl() {
    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    local global_opts=(-h --help -V --version -v --verbose --tmpdir --root)
    local config_opts=(
        --config --board --images-dir
        --vboot-keyblock --vboot-public-key --vboot-private-key
        --kernel-cmdline --ignore-initramfs
    )
    local cmds=(bless build config check list remove target write)

    case "$prev" in
        --root) _depthchargectl__root; _depthchargectl__disk; return ;;
        --root-mountpoint) _depthchargectl__file; return ;;
        --boot-mountpoint) _depthchargectl__file; return ;;
        --tmpdir) _depthchargectl__file; return ;;
        --config) _depthchargectl__file; return ;;
        --board) _depthchargectl__boards; return ;;
        --images-dir) _depthchargectl__file; return ;;
        --vboot-keyblock) _depthchargectl__file; return ;;
        --vboot-public-key) _depthchargectl__file; return ;;
        --vboot-private-key) _depthchargectl__file; return ;;
        --kernel-cmdline) _depthchargectl__cmdline; return ;;
        --ignore-initramfs) : ;;
        --zimage-initramfs-hack) COMPREPLY+=($(compgen -W "set-init-size pad-vmlinuz none" -- "$cur")) ;;
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
            if [ -f /etc/os-release ]; then
                local name="$(. /etc/os-release; echo "$NAME")"
                COMPREPLY+=($(compgen -W "$name" -- "$cur"))
            fi
            return
            ;;
        --root) _depthchargectl__root; _depthchargectl__disk; return ;;
        --compress)
            local compress=(none lz4 lzma)
            COMPREPLY+=($(compgen -W "${compress[*]}" -- "$cur"))
            return
            ;;
        --timestamp) _depthchargectl__timestamp; return;;
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
    local opts=(-a --all-disks -c --count -n --noheadings -o --output)
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
    local opts=(-s --min-size --allow-current -a --all-disks)
    local sizes=(8M 16M 32M 64M 128M 256M 512M)
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

# vim: filetype=sh
