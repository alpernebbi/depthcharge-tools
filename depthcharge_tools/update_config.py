#! /usr/bin/env python3

import configparser
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

# To write config sections in sort order
class SortedDict(collections.UserDict):
    def __iter__(self):
        return iter(sorted(self.data))


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

    def parse_defconfig(self, text):
        values = dict()

        for line in text.splitlines():
            if line.startswith("#"):
                continue

            lhs, sep, rhs = line.partition("=")
            if sep != "=" or not lhs.startswith("CONFIG_"):
                continue

            if rhs == "y":
                value = True
            elif rhs == "n":
                value = False
            elif rhs.startswith("0x"):
                value = int(rhs, 16)
            else:
                value = rhs.strip().strip("'\"")

            key = lhs[len("CONFIG_"):]
            values[key] = value

        return values

    @options.add
    @Argument("-d", "--depthcharge-repo", required=True)
    def depthcharge_repo(self, path):
        """\
        Chromium OS depthcharge firmware git repository

        https://chromium.googlesource.com/chromiumos/depthcharge
        """
        return Path(path)

    @property
    @lru_cache
    def depthcharge_boards(self):
        boards = {}

        for defconfig_f in self.depthcharge_repo.glob("board/*/defconfig"):
            defconfig = self.parse_defconfig(defconfig_f.read_text())

            # CONFIG_BOARD is removed in master
            board = defconfig.get("BOARD", defconfig_f.parent.name)

            # kevin, kevin-tpm2 both have BOARD="kevin", prefer former
            if board in boards and board != defconfig_f.parent.name:
                continue

            boards[board] = defconfig

        return boards

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

        # "snow" is the default, implicit "daisy"
        if board_relations.nodes().intersection(("snow", "daisy")):
            board_relations.add_edge("daisy", "snow")

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

        # Weird stuff from depthcharge
        for board, config in self.depthcharge_boards.items():
            parent = config.get("BOARD_DIR", None)
            if parent is None:
                continue

            board_relations.add_node(board)

            # src/board/ and BOARD_DIR has gru (baseboard) and veyron_*
            # (variants), we can't just always add "baseboard-".
            if "baseboard-{}".format(parent) in board_relations.nodes():
                parent = "baseboard-{}".format(parent)

            # This looks incorrect for a few boards, so only add the
            # relation if we don't know anything about the board
            if not board_relations.parents(board):
                if parent != board:
                    board_relations.add_edge(parent, board)

        # "veyron_rialto" doesn't show up anywhere as a child of veyron
        # but exists in depthcharge
        if "veyron_rialto" in board_relations.nodes():
            board_relations.add_edge("veyron", "veyron_rialto")

        return board_relations

    @options.add
    @Argument("-o", "--output", required=True)
    def output(self, path):
        """Write updated config to PATH."""

        if path is None:
            raise ValueError(
                "Output argument is required."
            )

        return Path(path).resolve()

    @property
    @lru_cache
    def board_config_sections(self):
        board_relations = self.board_relations

        # "project-*" overlays don't really look like boards.
        projects = set(
            overlay.name.partition("-")[2]
            for overlay in self.board_overlays_repo.glob("project-*")
        )
        nonboards = set((
            *projects,
            "unprovisioned",
            "signed",
            "embedded",
            "legacy",
            "npcx796",
            "npcx796fc",
            "ext_ec",
            "extec",
            "alc1015_amp",
        ))

        def get_parent(board):
            # Projects can be the sole parent of actual boards (e.g.
            # freon was to a lot of boards) so don't use them as parents
            # at all, despite breaking e.g. termina/tael parentage.
            parents = board_relations.parents(board) - nonboards
            if len(parents) > 1:
                raise ValueError(
                    "Board '{}' has multiple parents: '{}'"
                    .format(board, parents)
                )

            for parent in parents:
                return parent

        aliases = {}
        def add_alias(alias, board):
            if alias in aliases:
                aliases[alias] = None
            else:
                aliases[alias] = board

        # Do not alias nonboards to anything
        for nonboard in nonboards:
            aliases[nonboard] = None

        # Convert the nodes to the path-to-node format we want
        paths = {}
        for board in board_relations.nodes():
            parts = [board]
            parent = get_parent(board)

            if parent is not None:
                lhs, sep, rhs = board.partition("_")

                if sep != "_":
                    pass

                # Fixup left-duplication e.g. veyron/veyron_speedy
                elif lhs == parent:
                    parts = [rhs]
                    add_alias(rhs, board)

                # Fixup right-duplication e.g. hatch/unprovisioned_hatch
                elif rhs == parent:
                    parts = [lhs]
                    add_alias(lhs, board)

                # Split e.g. unprovisioned_kohaku -> kohaku/unprovisioned
                elif lhs in nonboards:
                    parts = [lhs, rhs]

                # Split e.g. arcada_signed -> arcada/signed
                elif lhs in nonboards:
                    parts = [rhs, lhs]

                # Split volteer2_ti50, helios_diskswap etc.
                else:
                    parts = list(reversed(board.split("_")))

            while parent is not None:
                parts.append(parent)
                parent = get_parent(parent)

            paths[board] = "boards/{}".format("/".join(reversed(parts)))

        for alias, board in aliases.items():
            if board is not None:
                paths.setdefault(alias, paths[board])

        return paths

    def __call__(self):
        config = configparser.ConfigParser(dict_type=SortedDict)

        for codename, blocks in self.recovery_conf_boards.items():
            name = self.board_config_sections.get(codename, None)

            if name is None:
                self.logger.warning(
                    "Can't figure a section name for board '{}'."
                    .format(codename)
                )
                name = "unknown/{}".format(codename)

            config.add_section(name)
            board = config[name]
            board["codename"] = codename

            for i, block in enumerate(blocks):
                if len(blocks) > 1:
                    name_i = "{}/{}".format(name, i)
                    config.add_section(name_i)
                    board = config[name_i]

                if block.get("hwidmatch", None):
                    board["hwid-match"] = block["hwidmatch"]

                if block.get("name", None):
                    board["name"] = block["name"]

        with self.output.open("x") as output_f:
            config.write(output_f)

if __name__ == "__main__":
    update_config.main()
