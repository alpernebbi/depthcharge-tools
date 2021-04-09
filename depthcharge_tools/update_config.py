#! /usr/bin/env python3

import collections
import json
import logging
import re

from functools import lru_cache
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

        if "filesize" in values:
            values["filesize"] = int(values["filesize"] or 0)
        if "zipfilesize" in values:
            values["zipfilesize"] = int(values["zipfilesize"] or 0)

        return values

    @options.add
    @Argument("-r", "--recovery-conf", required=True)
    def recovery_conf(self, path):
        """\
        Chrome OS recovery.conf file for their Linux recovery tool

        https://dl.google.com/dl/edgedl/chromeos/recovery/recovery.conf
        """
        return Path(path)

    @property
    @lru_cache
    def recovery_conf_boards(self):
        header, *blocks = [
            self.parse_recovery_conf_block(block)
            for block in re.split("\n\n+", self.recovery_conf.read_text())
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

        boards = collections.defaultdict(list)
        for block in blocks:
            hwidmatch = block.get("hwidmatch")

            # This might be a parent board, but the best fallback we have
            codename = block.get("file").split("_")[2]

            if hwidmatch == "duplicate of rabbid":
                codename = "rabbid"
                block["hwidmatch"] = None
            elif hwidmatch == "duplicate of C433":
                codename = "shyvana"
                block["hwidmatch"] = None
            elif hwidmatch == "Duplicate of BARLA":
                codename = "barla"
                block["hwidmatch"] = None

            elif hwidmatch.strip("^(").startswith("ACER ZGB"):
                pass # x86-zgb, x86-zgb-he
            elif hwidmatch.strip("^(").startswith("IEC MARIO"):
                pass # x86-mario
            elif hwidmatch.strip("^(").startswith("SAMS ALEX"):
                pass # x86-alex, x86-alex-he

            elif hwidmatch in (
                "DOES NOT MATCH ANYTHING",
                "NO MATCH JUST FOR ENTRY",
            ):
                codename = block.get("file").split("_")[2]
                block["hwidmatch"] = None

            else:
                m = re.match("^\^?\(?([0-9A-Z]+)[^0-9A-Za-z]", hwidmatch)
                if m:
                    codename = m.group(1).lower()
                else:
                    self.logger.warning(
                        "Could not parse codename for hwidmatch '{}'."
                        .format(hwidmatch)
                    )

            if codename:
                boards[codename].append(block)

        return dict(boards)

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

    @options.add
    @Argument("-b", "--board-overlays-repo", required=True)
    def board_overlays_repo(self, path):
        """\
        Chromium OS board-overlays git repository

        https://chromium.googlesource.com/chromiumos/overlays/board-overlays
        """
        return Path(path)

    def get_project_config_boards(self, d):
        children = set()

        project_config = (
            d / "sw_build_config" / "platform" / "chromeos-config"
            / "generated" / "project-config.json"
        )
        if project_config.is_file():
            config = json.loads(project_config.read_text())

            for section in config["chromeos"]["configs"]:
                if section["name"]:
                    children.add(section["name"])

        return children

    @options.add
    @Argument("-p", "--chromiumos-project-repo", required=True)
    def chromiumos_project_repo(self, path):
        """\
        Chromium OS's chromiumos/project git repository

        https://chromium.googlesource.com/chromiumos/project
        """
        return Path(path)

    @property
    @lru_cache
    def board_relations(self):
        board_relations = DirectedGraph()
        repo_names = {}

        # Find canonical names for each board
        for board_d in iterdir(self.board_overlays_repo):
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
            board_d = self.board_overlays_repo / overlay

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

        # "project-*" overlays don't really look like boards, but they
        # can be the sole parent of actual boards (e.g. freon was to a
        # lot of boards) so we can't just remove their descendants.
        projects = set(
            overlay.name.partition("-")[2]
            for overlay in self.board_overlays_repo.glob("project-*")
        )
        for project in projects:
            board_relations.remove_node(project)

        # Some newer board variants are only in this project repo
        for board in iterdir(self.chromiumos_project_repo):
            if not board.is_dir() or board.name.startswith("."):
                continue

            board_relations.add_node(board.name)

            for profile in iterdir(board):
                if not profile.is_dir() or profile.name.startswith("."):
                    continue

                # puff/puff exists
                if profile.name != board.name:
                    board_relations.add_edge(board.name, profile.name)

                for child in self.get_project_config_boards(profile):
                    # shadowkeep/shadowkeep/shadowkeep exists
                    if child == profile.name == board.name:
                        continue

                    # galaxy/{andromeda,sombrero} has galaxy
                    # make them {andromeda,sombrero}_galaxy
                    elif child == board.name:
                        child = "{}_{}".format(profile.name, child)

                    if child != profile.name:
                        board_relations.add_edge(profile.name, child)

        # Right now each node should have a single parent, so we can
        # turn them into a chipset-x/baseboard-y/z/t form by the parents
        multiparents = {
            board: board_relations.parents(board)
            for board in board_relations.nodes()
            if len(board_relations.parents(board)) > 1
        }
        if multiparents:
            raise ValueError(
                "The following boards have multiple parents: '{}'."
                .format(multiparents)
            )

        # Convert the nodes to the path-to-node format we want
        paths = {}
        for board in board_relations.nodes():
            parts = [board]
            parents = board_relations.parents(board)

            # There is at most one parent here
            for parent in parents:
                lhs, sep, rhs = board.partition("_")

                # Fixup duplication e.g. veyron/veyron_speedy
                if sep != "_":
                    pass
                elif lhs == parent:
                    parts = [rhs]
                elif rhs == parent:
                    parts = [lhs]

            while parents:
                parent = parents.pop()
                parts.append(parent)
                parents = board_relations.parents(parent)

            paths[board] = "/".join(reversed(parts))

        for board, path in paths.items():
            if board != path:
                board_relations.replace_node(board, path)

        return board_relations

    def __call__(self):
        pass


if __name__ == "__main__":
    update_config.main()
