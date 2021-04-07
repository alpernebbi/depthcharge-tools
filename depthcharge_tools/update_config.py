#! /usr/bin/env python3

import logging
import re

from pathlib import Path

from depthcharge_tools import __version__
from depthcharge_tools.utils.argparse import (
    Command,
    Argument,
    Group,
)
from depthcharge_tools.utils.collections import (
    DirectedGraph,
)
from depthcharge_tools.utils.pathlib import (
    iterdir,
    read_lines,
)

class update_config(
    Command,
    prog="update_config.py",
    add_help=False,
):
    """Maintainer tool to help update depthcharge-tools config.ini"""

    logger = logging.getLogger(__name__)

    @Group
    def options(self):
        """Options"""

    @options.add
    @Argument("-h", "--help", action="help")
    def print_help(self):
        """Show this help message."""
        # type(self).parser.print_help()

    @options.add
    @Argument(
        "-V", "--version",
        action="version",
        version="depthcharge-tools %(prog)s {}".format(__version__),
    )
    def version(self):
        """Print program version."""
        return type(self).version.version % {"prog": type(self).prog}

    @options.add
    @Argument("-v", "--verbose", count=True)
    def verbosity(self, verbosity=0):
        """Print more detailed output."""
        level = logging.WARNING - int(verbosity) * 10
        self.logger.setLevel(level)
        return verbosity

    def parse_recovery_conf_block(self, block):
        values = {}

        for line in block.splitlines():
            if line.startswith("#"):
                continue

            key, sep, value = line.partition("=")
            if sep != "=":
                raise ValueError(
                    "No equals sign in line: '{}'"
                    .format(line)
                )

            if key not in values:
                values[key] = value
            elif isinstance(values[key], list):
                values[key].append(value)
            else:
                values[key] = [values[key], value]

        if "hwidmatch" in values:
            values["hwidmatch"] = re.compile(values["hwidmatch"])
        if "filesize" in values:
            values["filesize"] = int(values["filesize"] or 0)
        if "zipfilesize" in values:
            values["zipfilesize"] = int(values["zipfilesize"] or 0)

        return values

    def parse_recovery_conf(self, path):
        recovery_conf = Path(path)

        header, *boards = [
            self.parse_recovery_conf_block(block)
            for block in re.split("\n\n+", recovery_conf.read_text())
        ]

        version = header.get(
            "recovery_tool_linux_version",
            header.get("recovery_tool_version"),
        )

        if version != "0.9.2":
            raise TypeError(
                "Unsupported recovery.conf version: {}"
                .format(header.get("recovery_tool_update", version))
            )

        return boards

    def read_profiles_repo_name(self, d):
        # A single-line file, so return the first line
        for line in read_lines(d / "profiles" / "repo_name"):
            return line.strip()

    def parse_layout_conf(self, d):
        values = {}

        for line in read_lines(d / "metadata" / "layout.conf"):
            key, eq, value = line.partition("=")
            if eq == "=" and "#" not in key:
                values[key.strip()] = value.strip()

        return values

    def get_profiles_base_parent_boards(self, d):
        parents = []

        for line in read_lines(d / "profiles" / "base" / "parent"):
            # Most end with :base, but there were e.g. freon:base/amd64
            lhs, sep, rhs = line.partition(":")
            if sep == ":" and rhs.startswith("base"):
                parents.append(lhs)

            # Very old scheme, e.g. firmware-snow-2695.B tegra variants
            prefix = "../../../"
            suffix = "/profiles/base"
            if line.startswith(prefix) and line.endswith(suffix):
                parents.append(line[len(prefix):-len(suffix)])

        return parents

    def get_model_yaml_boards(self, d):
        children = set()

        # chromeos-config-bsp directories can have inconsistent names.
        for config_d in d.glob("chromeos-base/chromeos-config-bsp*"):
            for line in read_lines(config_d / "files" / "model.yaml"):
                # A giant hack that lets me avoid parsing yaml
                keyname = "- $device-name:"
                space, sep, child = line.partition(keyname)
                if sep == keyname and "#" not in space:
                    children.add(child.strip().strip('\'"'))

        return children

    def analyze_board_overlays(self, path):
        board_relations = DirectedGraph()
        board_overlays = Path(path)
        repo_names = {}

        # Find canonical names for each board
        for board_d in iterdir(board_overlays):
            if not board_d.is_dir() or board_d.name.startswith("."):
                continue

            layout_conf = self.parse_layout_conf(board_d)
            repo_name = layout_conf.get("repo-name")

            # e.g. overlay-amd64-host doesn't have layout.conf
            if repo_name is None:
                repo_name = self.read_profiles_repo_name(board_d)

            if repo_name is None:
                self.logger.warning(
                    "Couldn't find a canonical name for board dir '{}'."
                    .format(board_d.name)
                )
                repo_name = board_d.name

            repo_names[board_d.name] = repo_name
            board_relations.add_node(repo_name)

        # Get parents after we have a name for every board, so that we can
        # ignore non-boards like chromiumos, portage-stable, eclass-overlay.
        def add_parent(parent, child):
            if parent != child and parent in board_relations.nodes():
                board_relations.add_edge(parent, child)

        for overlay, repo_name in repo_names.items():
            board_d = board_overlays / overlay

            for parent in self.get_profiles_base_parent_boards(board_d):
                add_parent(parent, repo_name)

            # Various model/skus of recent boards don't have explicit overlay
            # dirs, but are specified in model.yaml in the base overlay
            for child in self.get_model_yaml_boards(board_d):
                add_parent(repo_name, child)

            # Some relations only exists in layout.conf, e.g.
            # - x86-generic -> x86-generic_embedded
            # - project-* dirs and their children
            # - peach -> peach_pit in firmware-gru-8785.B
            layout_conf = self.parse_layout_conf(board_d)
            for parent in layout_conf.get("masters", "").split():
                add_parent(parent, repo_name)

        return board_relations

    def __call__(self):
        pass


if __name__ == "__main__":
    update_config.main()
