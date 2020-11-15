#! /usr/bin/env python3

import argparse
import logging
import sys
import types

from depthcharge_tools import __version__

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


def _print(**kwargs):
    print(kwargs)


depthchargectl = types.SimpleNamespace(
    build=_print,
    check=_print,
    partitions=_print,
    rm=_print,
    set_good=_print,
    target=_print,
    write=_print,
)


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Manage Chrome OS kernel partitions.",
        usage="%(prog)s [options] command ...",
        add_help=False
    )

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
            action='store_true',
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
        add_help=False,
    )
    build_options = build.add_argument_group(
        title="Options",
    )
    add_global_options(build_options)

    check = commands.add_parser(
        "check",
        description="Check if a depthcharge image can be booted.",
        help="Check if a depthcharge image can be booted.",
        add_help=False,
    )
    check_options = check.add_argument_group(
        title="Options",
    )
    add_global_options(check_options)

    partitions = commands.add_parser(
        "partitions",
        description="List ChromeOS kernel partitions.",
        help="List ChromeOS kernel partitions.",
        add_help=False,
    )
    partitions_options = partitions.add_argument_group(
        title="Options",
    )
    add_global_options(partitions_options)

    rm = commands.add_parser(
        "rm",
        description="Remove images and disable partitions containing them.",
        help="Remove images and disable partitions containing them.",
        add_help=False,
    )
    rm_options = rm.add_argument_group(
        title="Options",
    )
    add_global_options(rm_options)

    set_good = commands.add_parser(
        "set-good",
        description="Set the current partition as successfully booted.",
        help="Set the current partition as successfully booted.",
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
        add_help=False,
    )
    target_options = target.add_argument_group(
        title="Options",
    )
    add_global_options(target_options)

    write = commands.add_parser(
        "write",
        description="Write an image to a ChromeOS kernel partition.",
        help="Write an image to a ChromeOS kernel partition.",
        add_help=False,
    )
    write_options = write.add_argument_group(
        title="Options",
    )
    add_global_options(write_options)

    parser.set_defaults(command='partitions')

    return parser


if __name__ == "__main__":
    main()
