#! /usr/bin/env python3

import argparse
import logging
import sys
import types

from depthcharge_tools import __version__
from depthcharge_tools.utils import (
    Disk,
    Partition,
)

logger = logging.getLogger(__name__)


def main(*argv):
    if len(argv) == 0:
        prog, *argv = sys.argv

    parser = argument_parser()
    args = parser.parse_args(argv)
    command = getattr(depthchargectl, args.command.replace("-", "_"))
    kwargs = vars(args)
    del kwargs["command"]

    try:
        command(**kwargs)
    except ValueError as err:
        parser.error(err.args[0])


def _partitions(
    disks=None,
    headings=True,
    all_disks=False,
    output=None,
    verbose=None,
):
    if all_disks:
        disks = Disk.disks()
    elif disks:
        disks = Disk.disks(*disks)
    else:
        disks = Disk.disks(bootable=True)

    if output is None:
        output = "S,P,T,PATH"
    elif isinstance(output, list):
        output = ",".join(output)

    formats = {
        "SUCCESSFUL": "{0.successful}",
        "PRIORITY": "{0.priority}",
        "TRIES": "{0.tries}",
        "S": "{0.successful}",
        "P": "{0.priority}",
        "T": "{0.tries}",
        "PATH": "{0.path}",
        "DISKPATH": "{0.disk.path}",
        "PARTNO": "{0.partno}",
        "SIZE": "{0.size}",
    }

    columns = output.split(',')
    rows = []

    if headings:
        rows.append(list(columns))

    for disk in disks:
        for part in disk.partitions():
            row = [formats.get(c, "").format(part) for c in columns]
            rows.append(row)

    widths = [max(4, *map(len, col)) for col in zip(*rows)]
    fmt = " ".join("{{:{w}}}".format(w=w) for w in widths)
    for row in rows:
        print(fmt.format(*row))


def _target(
    disks=None,
    min_size=None,
    allow_current=False,
    verbose=False,
):
    if not disks:
        disks = Disk.disks(bootable=True)

    partitions = []
    for d in disks:
        try:
            partitions.append(Partition(d))
        except:
            partitions.extend(Disk(d).partitions())

    good_partitions = []
    for p in partitions:
        if min_size is not None and p.size < int(min_size):
            continue
        if not allow_current and p.path == Disk.by_kern_guid():
            continue
        good_partitions.append(p)

    good_partitions = sorted(
        good_partitions,
        key=lambda p: (p.successful, p.priority, p.tries, p.size),
    )

    if good_partitions:
        print(good_partitions[0])


def _print(**kwargs):
    print(kwargs)


depthchargectl = types.SimpleNamespace(
    build=_print,
    check=_print,
    partitions=_partitions,
    rm=_print,
    set_good=_print,
    target=_target,
    write=_print,
)


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Manage Chrome OS kernel partitions.",
        usage="%(prog)s [options] command ...",
        add_help=False
    )

    class VerboseAction(argparse.Action):
        __subparsers = []

        def __init__(self, option_strings, dest, subparser, nargs=None, **kwargs):
            super().__init__(option_strings, dest, nargs=0, **kwargs)
            self.__subparsers.append(subparser)

        def __call__(self, parser, namespace, values, option_string=None):
            namespace.verbose = True
            for subparser in self.__subparsers:
                subparser.set_defaults(verbose=True)

    def add_global_options(group):
        group.add_argument(
            "-h", "--help",
            action='help',
            help="Show this help message.",
        )
        group.add_argument(
            "--version",
            action='version',
            version="depthcharge-tools %(prog)s {}".format(__version__),
            help="Print program version.",
        )
        group.add_argument(
            "-v", "--verbose",
            action=VerboseAction,
            subparser=group,
            default=False,
            help="Print more detailed output.",
        )

    options = parser.add_argument_group(
        title="Options",
    )
    add_global_options(options)

    commands = parser.add_subparsers(
        title="Supported commands",
        dest="command",
        prog="depthchargectl",
    )

    build = commands.add_parser(
        "build",
        description="Buld a depthcharge image for the running system.",
        help="Buld a depthcharge image for the running system.",
        usage="%(prog)s [options] [kernel-version]",
        add_help=False,
    )
    build_arguments = build.add_argument_group(
        title="Positional arguments",
    )
    build_arguments.add_argument(
        "kernel_version",
        metavar="kernel-version",
        nargs="?",
        help="Installed kernel version to build an image for.",
    )
    build_options = build.add_argument_group(
        title="Options",
    )
    build_options.add_argument(
        "-a", "--all",
        action='store_true',
        help="Build images for all available kernel versions.",
    )
    build_options.add_argument(
        "-f", "--force",
        action='store_true',
        help="Rebuild images even if existing ones are valid.",
    )
    build_options.add_argument(
        "--reproducible",
        action='store_true',
        help="Try to build reproducible images.",
    )
    add_global_options(build_options)

    check = commands.add_parser(
        "check",
        description="Check if a depthcharge image can be booted.",
        help="Check if a depthcharge image can be booted.",
        usage="%(prog)s [options] image",
        add_help=False,
    )
    check_arguments = check.add_argument_group(
        title="Positional arguments",
    )
    check_arguments.add_argument(
        "image",
        nargs="?",
        help="Depthcharge image to check validity of.",
    )
    check_options = check.add_argument_group(
        title="Options",
    )
    add_global_options(check_options)

    partitions = commands.add_parser(
        "partitions",
        description="List ChromeOS kernel partitions.",
        help="List ChromeOS kernel partitions.",
        usage="%(prog)s [options] [disk ...]",
        add_help=False,
    )
    partitions_arguments = partitions.add_argument_group(
        title="Positional arguments",
    )
    partitions_arguments.add_argument(
        "disks",
        metavar="disk",
        nargs="*",
        help="Disks to check for ChromeOS kernel partitions.",
    )
    partitions_options = partitions.add_argument_group(
        title="Options",
    )
    partitions_options.add_argument(
        "-n", "--noheadings",
        dest="headings",
        action='store_false',
        help="Don't print column headings.",
    )
    partitions_options.add_argument(
        "-a", "--all-disks",
        action='store_true',
        help="List partitions on all disks.",
    )
    partitions_options.add_argument(
        "-o", "--output",
        metavar="COLUMNS",
        action='append',
        help="Comma separated list of columns to output.",
    )
    add_global_options(partitions_options)

    rm = commands.add_parser(
        "rm",
        description="Remove images and disable partitions containing them.",
        help="Remove images and disable partitions containing them.",
        usage="%(prog)s [options] (kernel-version | image)",
        add_help=False,
    )
    rm_arguments = rm.add_argument_group(
        title="Positional arguments",
    )
    rm_image_or_version = rm_arguments.add_mutually_exclusive_group(
            required=True,
    )
    rm_image_or_version.add_argument(
        "kernel-version",
        nargs="?",
        help="Installed kernel version to disable.",
    )
    rm_image_or_version.add_argument(
        "image",
        nargs="?",
        help="Depthcharge image to disable.",
    )
    rm_options = rm.add_argument_group(
        title="Options",
    )
    rm_options.add_argument(
        "-f", "--force",
        action='store_true',
        help="Allow removing the currently booted partition.",
    )
    add_global_options(rm_options)

    set_good = commands.add_parser(
        "set-good",
        description="Set the current partition as successfully booted.",
        help="Set the current partition as successfully booted.",
        usage="%(prog)s [options]",
        add_help=False,
    )
    set_good_options = set_good.add_argument_group(
        title="Options",
    )
    add_global_options(set_good_options)

    target = commands.add_parser(
        "target",
        description="Choose or validate a ChromeOS Kernel partition to use.",
        help="Choose or validate a ChromeOS Kernel partition to use.",
        usage="%(prog)s [options] [partition | disk ...]",
        add_help=False,
    )
    target_arguments = target.add_argument_group(
        title="Positional arguments",
    )
    target_arguments.add_argument(
        "partition",
        nargs=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help="Chrome OS kernel partition to validate.",
    )
    target_arguments.add_argument(
        "disks",
        nargs="*",
        help="Disks to search for an appropriate Chrome OS kernel partition.",
    )
    target_options = target.add_argument_group(
        title="Options",
    )
    target_options.add_argument(
        "-s", "--min-size",
        metavar="BYTES",
        action='store',
        help="Target partitions larger than this size.",
    )
    target_options.add_argument(
        "--allow-current",
        action='store_true',
        help="Allow targeting the currently booted partition.",
    )
    add_global_options(target_options)

    write = commands.add_parser(
        "write",
        description="Write an image to a ChromeOS kernel partition.",
        help="Write an image to a ChromeOS kernel partition.",
        usage="%(prog)s [options] (kernel-image | image)",
        add_help=False,
    )
    write_arguments = write.add_argument_group(
        title="Positional arguments",
    )
    write_image_or_version = write_arguments.add_mutually_exclusive_group(
            required=True,
    )
    write_image_or_version.add_argument(
        "kernel-version",
        nargs="?",
        help="Installed kernel version to write to disk.",
    )
    write_image_or_version.add_argument(
        "image",
        nargs="?",
        help="Depthcharge image to write to disk.",
    )
    write_options = write.add_argument_group(
        title="Options",
    )
    write_options.add_argument(
        "-f", "--force",
        action='store_true',
        help="Write image even if it cannot be verified.",
    )
    write_options.add_argument(
        "-t", "--target",
        metavar="DISK|PART",
        action='store',
        help="Specify a disk or partition to write to.",
    )
    write_options.add_argument(
        "--no-prioritize",
        dest="prioritize",
        action='store_false',
        help="Don't set any flags on the partition.",
    )
    write_options.add_argument(
        "--allow-current",
        action='store_true',
        help="Allow overwriting the currently booted partition.",
    )
    add_global_options(write_options)

    parser.set_defaults(command='partitions')

    return parser


if __name__ == "__main__":
    main()
