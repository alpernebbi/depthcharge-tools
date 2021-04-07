#! /usr/bin/env python3

import configparser
import collections
import json
import logging
import re

from pathlib import Path

from depthcharge_tools.utils.collections import (
    DirectedGraph,
)
from depthcharge_tools.utils.pathlib import (
    iterdir,
    read_lines,
)

logger = logging.getLogger(__name__)


def analyze_board_overlays(path):
    board_relations = DirectedGraph()
    board_overlays = Path(path)
    repo_names = {}

    def parse_layout_conf(d):
        values = {}

        for line in read_lines(d / "metadata" / "layout.conf"):
            key, eq, value = line.partition("=")
            if eq == "=" and "#" not in key:
                values[key.strip()] = value.strip()

        return values

    def read_profiles_repo_name(d):
        # A single-line file, so return the first line
        for line in read_lines(d / "profiles" / "repo_name"):
            return line.strip()

    def get_profiles_base_parent_boards(d):
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

    def get_model_yaml_boards(d):
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

    # Find canonical names for each board
    for board_d in iterdir(board_overlays):
        if not board_d.is_dir() or board_d.name.startswith("."):
            continue

        layout_conf = parse_layout_conf(board_d)
        repo_name = layout_conf.get("repo-name")

        # e.g. overlay-amd64-host doesn't have layout.conf
        if repo_name is None:
            repo_name = read_profiles_repo_name(board_d)

        if repo_name is None:
            logger.warning(
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

        for parent in get_profiles_base_parent_boards(board_d):
            add_parent(parent, repo_name)

        # Various model/skus of recent boards don't have explicit overlay
        # dirs, but are specified in model.yaml in the base overlay
        for child in get_model_yaml_boards(board_d):
            add_parent(repo_name, child)

        # Some relations only exists in layout.conf, e.g.
        # - x86-generic -> x86-generic_embedded
        # - project-* dirs and their children
        # - peach -> peach_pit in firmware-gru-8785.B
        layout_conf = parse_layout_conf(board_d)
        for parent in layout_conf.get("masters", "").split():
            add_parent(parent, repo_name)

    return board_relations


def analyze_chromiumos_project(path):
    board_relations = DirectedGraph()
    project = Path(path)

    def get_project_config_boards(d):
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

    for board in iterdir(project):
        if not board.is_dir() or board.name.startswith("."):
            continue

        for profile in iterdir(board):
            if not profile.is_dir() or profile.name.startswith("."):
                continue

            # puff/puff exists
            if profile.name != board.name:
                board_relations.add_edge(board.name, profile.name)

            for child in get_project_config_boards(profile):
                # galaxy/{andromeda,sombrero} has galaxy
                if child != profile.name and child != board.name:
                    board_relations.add_edge(profile.name, child)

    return board_relations
