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
