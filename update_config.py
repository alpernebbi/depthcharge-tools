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
    SortedDict,
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
    """
    Maintainer tool to help update depthcharge-tools config.ini

    ---

    If you're packaging depthcharge-tools, don't use this as a build
    step. Results from this are intended to be checked and modified
    manually before they go into the final config.ini, the file
    committed to the repository is the canonical one.
    """

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
    @Argument("-r", "--recovery-conf")
    def recovery_conf(self, path=None):
        """\
        Chrome OS recovery.conf file for their Linux recovery tool

        https://dl.google.com/dl/edgedl/chromeos/recovery/recovery.conf
        """
        return Path(path) if path else None

    @property
    @lru_cache
    def recovery_conf_boards(self):
        if self.recovery_conf is None:
            return {}

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
    @Argument("-b", "--board-overlays-repo")
    def board_overlays_repo(self, path=None):
        """\
        Chromium OS board-overlays git repository

        https://chromium.googlesource.com/chromiumos/overlays/board-overlays
        """
        return Path(path) if path else None

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
    @Argument("-p", "--chromiumos-project-repo")
    def chromiumos_project_repo(self, path=None):
        """\
        Chromium OS's chromiumos/project git repository

        https://chromium.googlesource.com/chromiumos/project
        """
        return Path(path) if path else None

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

        # Not going to parse Kconfig for this
        if values.get("ARCH_ARM") and not values.get("ARCH_ARM_V8"):
            values["ARCH_ARM_V7"] = True

        return values

    @options.add
    @Argument("-d", "--depthcharge-repo")
    def depthcharge_repo(self, path=None):
        """\
        Chromium OS depthcharge firmware git repository

        https://chromium.googlesource.com/chromiumos/platform/depthcharge
        """
        return Path(path) if path else None

    def parse_kconfig_defaults(self, text):
        defaults = {}

        clean_text, _ = re.subn("#.*\n", "\n", text)
        blocks = re.split("\n\n+", clean_text)
        for block in blocks:
            config = None

            for line in block.splitlines():
                line = line.strip()

                if not line or line.startswith("help"):
                    if config is None:
                        continue
                    else:
                        config = None
                        break

                m = re.match("config ([0-9A-Z_]+)", line)
                if m:
                    config = m.group(1)
                    type_ = lambda s: str.strip(s, "'\"")
                    defaults[config] = {}

                if config is None:
                    continue

                if line.startswith("hex"):
                    type_ = lambda x: int(x, 16)
                elif line.startswith("int"):
                    type_ = int
                elif line.startswith("bool"):
                    type_ = lambda b: b in ("y", "Y")
                elif line.startswith("string"):
                    type_ = lambda s: str.strip(s, "'\"")

                m = re.match("default (\S+|\".+\")$", line)
                try:
                    value = type_(m.group(1).strip("'\""))
                except ValueError:
                    value = m.group(1)
                except AttributeError:
                    value = None
                finally:
                    if value is not None:
                        defaults[config][None] = value
                    value = None

                m = re.match("default (\S+|\".+\") if ([0-9A-Z_]+)", line)
                try:
                    value = type_(m.group(1))
                    cond = m.group(2)
                except ValueError:
                    value = m.group(1)
                    cond = m.group(2)
                except AttributeError:
                    value = None
                    cond = None
                finally:
                    if value is not None and cond is not None:
                        defaults[config][cond] = value
                    value = None

        return defaults

    def parse_kconfig_selects(self, text):
        selects = {}

        clean_text, _ = re.subn("#.*\n", "\n", text)
        blocks = re.split("\n\n+", clean_text)
        for block in blocks:
            config = None

            for line in block.splitlines():
                line = line.strip()

                if not line or line.startswith("help"):
                    if config is None:
                        continue
                    else:
                        config = None
                        break

                m = re.match("config ([0-9A-Z_]+)", line)
                if m:
                    config = m.group(1)
                    type_ = lambda s: str.strip(s, "'\"")
                    selects[config] = {}
                    selects[config][None] = []

                if config is None:
                    continue

                m = re.match("select (\S+|\".+\")$", line)
                if m:
                    value = m.group(1).strip("'\"")
                    selects[config][None].append(value)

                m = re.match("select (\S+|\".+\") if ([0-9A-Z_]+)", line)
                if m:
                    value = m.group(1)
                    cond = m.group(2)
                    if cond not in selects[config]:
                        selects[config][cond] = []
                    selects[config][cond].append(value)

        return selects

    @property
    @lru_cache
    def depthcharge_boards(self):
        boards = {}
        defaults = collections.defaultdict(dict)

        if self.depthcharge_repo is None:
            return boards

        # Provide a limited set of default values to avoid having to
        # parse all Kconfig files or something
        image_f = self.depthcharge_repo / "src/image/Kconfig"
        image_d = self.parse_kconfig_defaults(image_f.read_text())

        for cond, default in image_d.get("KERNEL_SIZE", {}).items():
            defaults[cond]["KERNEL_SIZE"] = default

        for defconfig_f in self.depthcharge_repo.glob("board/*/defconfig"):
            defconfig = self.parse_defconfig(defconfig_f.read_text())

            # CONFIG_BOARD is removed in master
            board = defconfig.get("BOARD", defconfig_f.parent.name)

            # kevin, kevin-tpm2 both have BOARD="kevin", prefer former
            if board in boards and board != defconfig_f.parent.name:
                continue

            board_d = {}
            board_d.update(defaults.get(None, {}))
            for cond, config in defaults.items():
                if cond and defconfig.get(cond, None):
                    board_d.update(config)

            board_d.update(defconfig)
            boards[board] = board_d

        return boards

    @options.add
    @Argument("-c", "--coreboot-repo")
    def coreboot_repo(self, path=None):
        """\
        Chromium OS coreboot firmware git repository

        https://chromium.googlesource.com/chromiumos/third_party/coreboot
        """
        return Path(path) if path else None

    @property
    @lru_cache
    def coreboot_boards(self):
        boards = {}

        if self.coreboot_repo is None:
            return boards

        def get_board_name(config):
            parts = config.split("_")
            if len(parts) < 2 or parts[0] != "BOARD":
                return None

            vendor = parts[1].lower()
            if not (self.coreboot_repo / "src/mainboard" / vendor).is_dir():
                return None

            board = "_".join(config.split("_")[2:]).lower()
            return board

        for kconfig_f in self.coreboot_repo.glob("src/mainboard/*/*/Kconfig"):
            kconfig_name = kconfig_f.with_name("Kconfig.name")
            kconfig = kconfig_f.read_text()
            if kconfig_name.is_file():
                kconfig_name = kconfig_name.read_text()
            else:
                kconfig_name = ""

            defaults = self.parse_kconfig_defaults(kconfig)
            selects = self.parse_kconfig_selects(kconfig)
            selects.update(self.parse_kconfig_selects(kconfig_name))

            def add_board(config):
                board = get_board_name(config)
                if board in boards:
                    return boards[board]

                boards[board] = {}

                for cond, selectlist in selects.get(config, {}).items():
                    if cond is None or cond in boards[board]:
                        for select in selectlist:
                            if get_board_name(select):
                                boards[board].update(add_board(select))
                            boards[board][select] = True

                for key, values in defaults.items():
                    if get_board_name(key):
                        continue
                    value = values.get(config, values.get(None))
                    if value is not None:
                        boards[board][key] = value

                board_opts = selects.get("BOARD_SPECIFIC_OPTIONS", {})
                for cond, selectlist in board_opts.items():
                    if cond is None or cond in boards[board]:
                        for select in selectlist:
                            if get_board_name(select):
                                boards[board].update(add_board(select))
                            boards[board][select] = True

                boards[board][config] = True

                return boards[board]

            for config, _ in defaults.items():
                if get_board_name(config):
                    add_board(config)

            for select, _ in selects.items():
                if get_board_name(select):
                    add_board(select)

        for board, block in list(boards.items()):
            suffix = "_common"
            if board.endswith(suffix):
                actual = board[:-len(suffix)]
                boards.setdefault(actual, boards.pop(board))
                board = actual

            prefix = "baseboard_"
            if board.startswith(prefix):
                actual = "baseboard-{}".format(board[len(prefix):])
                boards.setdefault(actual, boards.pop(board))
                board = actual

            if not block.get("MAINBOARD_HAS_CHROMEOS", False):
                if board in boards:
                    boards.pop(board)
                continue

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

        for overlay, repo_name in repo_names.items():
            board_d = self.board_overlays_repo / overlay

            for parent in self.get_profiles_base_parent_boards(board_d):
                if parent != repo_name:
                    board_relations.add_edge(parent, repo_name)

            # Various model/skus of recent boards don't have explicit overlay
            # dirs, but are specified in model.yaml in the base overlay
            for child in self.get_model_yaml_boards(board_d):
                if repo_name != child:
                    board_relations.add_edge(repo_name, child)

            # Some relations only exists in layout.conf, e.g.
            # - x86-generic -> x86-generic_embedded
            # - project-* dirs and their children
            # - peach -> peach_pit in firmware-gru-8785.B
            layout_conf = self.parse_layout_conf(board_d)
            for parent in layout_conf.get("masters", "").split():
                if parent != repo_name and parent not in (
                    "chromiumos",
                    "portage-stable",
                    "eclass-overlay",
                ):
                    board_relations.add_edge(parent, repo_name)

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

        # Project repo lists all "veyron" boards under "veyron-pinky"
        if "veyron-pinky" in board_relations.nodes():
            board_relations.add_edge("veyron", "veyron-pinky")
            for child in board_relations.children("veyron-pinky"):
                board_relations.add_edge("veyron", child)
                board_relations.remove_edge("veyron-pinky", child)

        # Weird stuff from depthcharge
        for board, config in self.depthcharge_boards.items():
            parent = config.get("BOARD", None)
            parent = config.get("BOARD_DIR", parent)
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

        nodes = {
            node.replace("-", "_"): node
            for node in board_relations.nodes()
        }

        def coreboot_board_name(config):
            if config is None or not config.startswith("BOARD_"):
                return None

            board = "_".join(config.split("_")[2:]).lower()
            if board.startswith("baseboard_"):
                board = "baseboard-{}".format(board[len("baseboard_"):])

            if board not in self.coreboot_boards:
                return None

            return board

        def add_coreboot_parents(board):
            if board is None:
                return None

            board = nodes.get(board.replace("-", "_"), board)
            board_relations.add_node(board)

            block = self.coreboot_boards.get(board, {})
            parents = set(
                coreboot_board_name(config)
                for config, value in block.items()
                if value
            )

            for parent in parents - {board, None}:
                add_coreboot_parents(parent)
                parent = nodes.get(parent.replace("-", "_"), parent)

                # This also has conflicts with board-overlays
                if not board_relations.parents(board):
                    board_relations.add_edge(parent, board)

        for board, block in self.coreboot_boards.items():
            add_coreboot_parents(board)

        nodes = {
            node.replace("_", "-"): node
            for node in board_relations.nodes()
        }

        # Recovery.conf heuristics, doesn't have actual parent board info
        for board, blocks in self.recovery_conf_boards.items():
            parents = set([b.get("file").split("_")[2] for b in blocks])
            parents.discard(board)
            if len(parents) > 1:
                continue
            elif len(parents) == 0:
                parent = None
            else:
                parent = parents.pop()

            # This is really inaccurate with underscores replaced with
            # hyphens, so only use it if we don't know anything else
            if board in nodes:
                continue

            # Don't duplicate veyron_speedy as speedy
            if parent in nodes:
                parent = nodes[parent]
            if parent and parent.endswith(board):
                parent = parent[:-len(board)-1]

            board_relations.add_node(board)
            if parent:
                board_relations.add_edge(parent, board)

        # Add board architectures as root parent
        for board, config in self.depthcharge_boards.items():
            if config.get("ARCH_X86"):
                arch = "amd64"
            elif config.get("ARCH_ARM_V8"):
                arch = "arm64"
            elif config.get("ARCH_ARM"):
                arch = "arm"
            else:
                continue

            roots = board_relations.roots(board)
            for root in roots - {"x86", "amd64", "arm64", "arm"}:
                board_relations.add_edge(arch, root)

        # Baseboards, chipsets shouldn't depend on others in their class
        for board in board_relations.nodes():
            if board.startswith("chipset-"):
                for child in board_relations.children(board):
                    if child.startswith("chipset-"):
                        board_relations.remove_edge(board, child)
                        for parent in board_relations.parents(board):
                            board_relations.add_edge(parent, child)

            elif board.startswith("baseboard-"):
                for child in board_relations.children(board):
                    if child.startswith("baseboard-"):
                        board_relations.remove_edge(board, child)
                        for parent in board_relations.parents(board):
                            board_relations.add_edge(parent, child)

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
        if self.board_overlays_repo is not None:
            projects = set(
                overlay.name.partition("-")[2]
                for overlay in self.board_overlays_repo.glob("project-*")
            )
        else:
            projects = set()

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

        chipsets = {
            "chipset-adl": "alderlake",
            "chipset-adln": "alderlake-n",
            "chipset-apl": "apollolake",
            "chipset-bdw": "broadwell",
            "chipset-bsw": "braswell",
            "chipset-byt": "baytrail",
            "chipset-cml": "cometlake",
            "chipset-cnl": "cannonlake",
            "chipset-glk": "geminilake",
            "chipset-hsw": "haswell",
            "chipset-icl": "icelake",
            "chipset-ivb": "ivybridge",
            "chipset-jsl": "jasperlake",
            "chipset-kbl": "kabylake",
            "chipset-mtl": "meteorlake",
            "chipset-rpl": "raptorlake",
            "chipset-skl": "skylake",
            "chipset-snb": "sandybridge",
            "chipset-tgl": "tigerlake",
            "chipset-whl": "whiskeylake",
            "chipset-stnyridge": "stoneyridge",
        }

        def get_parent(board):
            # Projects can be the sole parent of actual boards (e.g.
            # freon was to a lot of boards) so don't use them as parents
            # at all, despite breaking e.g. termina/tael parentage.
            parents = board_relations.parents(board) - nonboards
            if len(parents) > 1:
                self.logger.warning(
                    "Board '{}' has multiple parents: '{}'"
                    .format(board, parents)
                )
            elif len(parents) == 0:
                return None

            # Prefer longer chains
            return max(
                parents,
                key=lambda p: len(board_relations.ancestors(p)),
            )

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

            # Prefer full names for chipsets
            if board.startswith("chipset-"):
                chipset = chipsets.get(board, board[len("chipset-"):])
                parts = [chipset]

            # Don't keep baseboard prefix
            if board.startswith("baseboard-"):
                baseboard = board[len("baseboard-"):]
                parts = [baseboard]

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

                # e.g. arcada_signed, volteer2_ti50, helios_diskswap etc.
                else:
                    parts = [rhs, lhs]

            while parent is not None:
                # Prefer full names for chipsets
                if parent.startswith("chipset-"):
                    chipset = chipsets.get(parent, parent[len("chipset-"):])
                    parts.append(chipset)

                # Normalize boards with the same name as baseboard
                elif parent.startswith("baseboard-"):
                    baseboard = parent[len("baseboard-"):]
                    if parts[-1] != baseboard:
                        parts.append(baseboard)

                else:
                    parts.append(parent)

                parent = get_parent(parent)

            paths[board] = "boards/{}".format("/".join(reversed(parts)))

        for alias, board in aliases.items():
            if board is not None:
                paths.setdefault(alias, paths[board])

        return paths

    def __call__(self):
        config = configparser.ConfigParser(
            dict_type=SortedDict(lambda s: s.split('/')),
        )

        for arch in ("x86", "amd64", "arm", "arm64"):
            name = self.board_config_sections.get(arch, None)
            if name is None:
                continue

            config.add_section(name)
            config[name]["arch"] = arch
            config[name]["codename"] = "{}-generic".format(arch)

        for board, name in self.board_config_sections.items():
            if board.startswith("chipset-"):
                config.add_section(name)
                config[name]["codename"] = board

        for codename, blocks in self.recovery_conf_boards.items():
            name = self.board_config_sections.get(codename, None)
            if name is None:
                continue

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

        # Some heuristics for kernel compression
        if self.depthcharge_repo is not None:
            arm64_boot_c = (self.depthcharge_repo / "src/arch/arm/boot64.c")
            if arm64_boot_c.is_file():
                arm64_boot_c = arm64_boot_c.read_text()
            else:
                arm64_boot_c = ""

            fit_c = (self.depthcharge_repo / "src/boot/fit.c")
            if fit_c.is_file():
                fit_c = fit_c.read_text()
            else:
                fit_c = ""

            fit_h = (self.depthcharge_repo / "src/boot/fit.h")
            if fit_h.is_file():
                fit_h = fit_h.read_text()
            else:
                fit_h = ""

        else:
            arm64_boot_c = ""
            fit_c = ""
            fit_h = ""

        if "fit_decompress(kernel" in arm64_boot_c:
            arm64_lz4_kernel = "CompressionLz4" in fit_h + fit_c
            arm64_lzma_kernel = "CompressionLzma" in fit_h + fit_c
        elif "switch(kernel->compression)" in arm64_boot_c:
            arm64_lz4_kernel = "case CompressionLz4" in arm64_boot_c
            arm64_lzma_kernel = "case CompressionLzma" in arm64_boot_c
        else:
            arm64_lz4_kernel = False
            arm64_lzma_kernel = False

        for codename, block in self.depthcharge_boards.items():
            name = self.board_config_sections.get(codename, None)
            if name is None:
                name = codename
            if name not in config:
                config.add_section(name)

            board = config[name]
            board["codename"] = codename

            if block.get("KERNEL_SIZE", None):
                board["image-max-size"] = str(block["KERNEL_SIZE"])

            if block.get("KERNEL_FIT", False):
                board["image-format"] = "fit"
            elif block.get("KERNEL_ZIMAGE", False):
                board["image-format"] = "zimage"

            if block.get("ARCH_ARM_V8", False):
                board["boots-lz4-kernel"] = str(arm64_lz4_kernel)
                board["boots-lzma-kernel"] = str(arm64_lzma_kernel)

            # compatible string
            board_c = (
                self.depthcharge_repo / "src/board"
                / codename / "board.c"
            )
            board_c = board_c.read_text() if board_c.is_file() else ""
            if block.get("KERNEL_FIT", False):
                m = re.search(
                    'fit_(?:add|set)_compat(?:_by_rev)?\('
                    '"([^"]+?)(?:-rev[^-]+|-sku[^-]+)*"',
                    board_c,
                )
                if m:
                    board["dt-compatible"] = m.group(1)

                elif "sprintf(compat, pattern, CONFIG_BOARD," in fit_c:
                    board["dt-compatible"] = "google,{}".format(
                        block.get("BOARD", codename).lower()
                        .replace("_", "-").replace(" ", "-")
                    )

                elif '"google,%s", mb_part_string' in fit_c:
                    block = self.coreboot_boards.get(codename, {})
                    mb_part_string = block.get(
                        "MAINBOARD_PART_NUMBER",
                        codename,
                    )
                    board["dt-compatible"] = "google,{}".format(
                        mb_part_string.lower()
                        .replace("_", "-").replace(" ", "-")
                    )

        with self.output.open("x") as output_f:
            config.write(output_f)

if __name__ == "__main__":
    update_config.main()
