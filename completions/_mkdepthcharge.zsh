#compdef mkdepthcharge

function _mkdepthcharge {
    _arguments -S \
        {-h,--help}'[Show a help message.]' \
        {-v,--verbose}'[Print more detailed output.]' \
        --version'[Print program version.]' \
        {-o,--output}'[Write resulting image to FILE.]:output:_files' \
        {-A,--arch}'[Architecture to build for.]:arch:(arm arm64 aarch64 x86 x86_64 amd64)' \
        --format'[Kernel image format to use.]:format:(fit zimage)' \
        {-C,--compress}'[Compress vmlinuz with lz4 or lzma.]:compression:(none lz4 lzma)' \
        {-n,--name}'[Description of vmlinuz to put in the FIT.]:description: ' \
        '*'{-c,--cmdline}'[Command-line parameters for the kernel.]:kernel cmdline:{_mkdepthcharge__cmdline}' \
        --no-kern-guid'[Do not prepend kern_guid=%U to the cmdline.]' \
        --bootloader'[Bootloader stub binary to use.]:bootloader file:_files' \
        --devkeys'[Directory containing developer keys to use.]:devkeys dir:_directories' \
        --keyblock'[The key block file (.keyblock).]:keyblock file:_files' \
        --signprivate'[Private key (.vbprivk) to sign the image.]:vbprivk file:_files' \
        ':vmlinuz file:_files' \
        '*:initrd or dtb files:_files' \
        ;
}

function _mkdepthcharge__cmdline {
    local cmdline=($(cat /proc/cmdline | sed -e 's/\(cros_secure\|kern_guid\)[^ ]* //g'))
    _describe 'kernel cmdline' cmdline
}

_mkdepthcharge "$@"
