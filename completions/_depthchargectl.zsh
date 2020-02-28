#compdef depthchargectl

function _depthchargectl {
    _arguments -C \
        {-h,--help}'[Show a help message.]' \
        {-v,--verbose}'[Print more detailed output.]' \
        --version'[Print program version.]' \
        '1:command:(build check partitions rm set-good target write)' \
        '*::arg:->args' \
        ;

    case "$state:$line[1]" in
        args:build)
            _arguments -S \
                {-a,--all}'[Rebuild images for all kernel versions.]' \
                {-f,--force}'[Rebuild images even if unnecessary,]' \
                --reproducible'[Try to build a reproducible image.]' \
                ':kernel version:{_depthchargectl__kernel}' \
                ;
            ;;
        args:check)
            _arguments -S \
                ':image file:_files' \
                ;
            ;;
        args:partitions)
            local outputspec='{_values -s , "description" "S" "SUCCESSFUL" "T" "TRIES" "P" "PRIORITY" "DEVICE" "SIZE"}'
            _arguments -S \
                {-n,--noheadings}'[Do not print column headings.]' \
                {-a,--all-disks}'[list partitions on all disks.]' \
                {-o,--output}'[Comma separated list of columns to output.]:columns:'"$outputspec" \
                '*::disk or partition:{_depthchargectl__disk}' \
                ;
            ;;
        args:rm)
            _arguments -S \
                {-f,--force}'[Allow removing the current partition.]' \
                '::kernel version or image file:{_depthchargectl__kernel; _files}' \
                ;
            ;;
        args:set-good)
            : # No options or arguments
            ;;
        args:target)
            _arguments -S \
                {-s,--min-bytes}'[Target partitions larger than this size.]:bytes:(16777216 33554432)' \
                --allow-current'[Allow targeting the currently booted part.]' \
                '*::disk or partition:{_depthchargectl__disk}' \
                ;
            ;;
        args:write)
            _arguments -S \
                {-f,--force}'[Write image even if it cannot be verified.]' \
                {-t,--target}'[Specify a disk or partition to write to.]:disk or partition:{_depthchargectl__disk}' \
                --no-prioritize'[Do not set any flags on the partition]' \
                --allow-current'[Allow overwriting the current partition]' \
                '::kernel version or image file:{_depthchargectl__kernel; _files}' \
                ;
            ;;
        *) : ;;
    esac

}

function _depthchargectl__kernel {
    if command -v linux-version >/dev/null 2>/dev/null; then
        local kversions=($(linux-version list))
        _describe 'kernel version' kversions
    fi
}

function _depthchargectl__disk {
    local disks=($(lsblk -o NAME -n -l))
    _describe 'disk or partition' disks
}

_depthchargectl "$@"
