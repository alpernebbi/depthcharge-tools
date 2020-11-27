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
from depthcharge_tools.depthchargectl import (
    build,
    check,
    partitions,
    rm,
    set_good,
    target,
    write,
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


depthchargectl = types.SimpleNamespace(
    build=build._build,
    check=check._check,
    partitions=partitions._partitions,
    rm=rm._rm,
    set_good=set_good._set_good,
    target=target._target,
    write=write._write,
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

    build.argument_parser(commands, add_global_options)
    check.argument_parser(commands, add_global_options)
    partitions.argument_parser(commands, add_global_options)
    rm.argument_parser(commands, add_global_options)
    set_good.argument_parser(commands, add_global_options)
    target.argument_parser(commands, add_global_options)
    write.argument_parser(commands, add_global_options)

    parser.set_defaults(command='partitions')

    return parser


if __name__ == "__main__":
    main()
