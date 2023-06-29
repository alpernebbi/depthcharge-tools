#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools subprocess utilities
# Copyright (C) 2020-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

import contextlib
import logging
import re
import subprocess
import shlex

from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessRunner:
    def __init__(self, *args_prefix, **kwargs_defaults):
        self.args_prefix = args_prefix
        self.kwargs_defaults = {
            'encoding': "utf-8",
            'check': True,
        }
        self.kwargs_defaults.update(kwargs_defaults)

    def __call__(self, *args_suffix, **kwargs_overrides):
        args = (*self.args_prefix, *args_suffix)
        kwargs = {**self.kwargs_defaults, **kwargs_overrides}

        with contextlib.ExitStack() as ctx:
            stdin = kwargs.get("stdin", None)
            if isinstance(stdin, str):
                stdin = Path(stdin)
            if isinstance(stdin, bytes):
                kwargs["stdin"] = None
                kwargs["encoding"] = None
                kwargs["input"] = stdin
            if isinstance(stdin, Path):
                kwargs["stdin"] = ctx.enter_context(stdin.open("r"))
            if stdin is None:
                kwargs["stdin"] = subprocess.PIPE

            stdout = kwargs.get("stdout", None)
            if isinstance(stdout, str):
                stdout = Path(stdout)
            if isinstance(stdout, Path):
                kwargs["stdout"] = ctx.enter_context(stdout.open("x"))
            if stdout is None:
                kwargs["stdout"] = subprocess.PIPE

            stderr = kwargs.get("stderr", None)
            if isinstance(stderr, str):
                stderr = Path(stderr)
            if isinstance(stderr, Path):
                kwargs["stderr"] = ctx.enter_context(stderr.open("x"))
            if stderr is None:
                kwargs["stderr"] = subprocess.PIPE

            try:
                return subprocess.run(args, **kwargs)
            except subprocess.CalledProcessError as err:
                our_err = self._parse_subprocess_error(err)
                if our_err is None:
                    return subprocess.CompletedProcess(
                        args=err.cmd,
                        returncode=err.returncode,
                        stdout=err.stdout,
                        stderr=err.stderr,
                    )
                if our_err is not err:
                    raise our_err
                raise

    def _parse_subprocess_error(self, err):
        return err


class GzipRunner(ProcessRunner):
    def __init__(self):
        super().__init__("gzip", encoding=None)

    def compress(self, src, dest=None):
        proc = self("-c", "-6", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def decompress(self, src, dest=None):
        proc = self("-c", "-d", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def test(self, path):
        proc = self("-t", stdin=path, check=False)
        return proc.returncode == 0


class Lz4Runner(ProcessRunner):
    def __init__(self):
        super().__init__("lz4", encoding=None)

    def compress(self, src, dest=None):
        proc = self("-z", "-9", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def decompress(self, src, dest=None):
        proc = self("-d", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def test(self, path):
        proc = self("-t", stdin=path, check=False)
        return proc.returncode == 0


class LzmaRunner(ProcessRunner):
    def __init__(self):
        super().__init__("lzma", encoding=None)

    def compress(self, src, dest=None):
        proc = self("-z", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def decompress(self, src, dest=None):
        proc = self("-d", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def test(self, path):
        proc = self("-t", stdin=path, check=False)
        return proc.returncode == 0


class LzopRunner(ProcessRunner):
    def __init__(self):
        super().__init__("lzop", encoding=None)

    def compress(self, src, dest=None):
        proc = self("-c", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def decompress(self, src, dest=None):
        proc = self("-c", "-d", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def test(self, path):
        proc = self("-t", stdin=path, check=False)
        return proc.returncode == 0


class Bzip2Runner(ProcessRunner):
    def __init__(self):
        super().__init__("bzip2", encoding=None)

    def compress(self, src, dest=None):
        proc = self("-c", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def decompress(self, src, dest=None):
        proc = self("-c", "-d", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def test(self, path):
        proc = self("-t", stdin=path, check=False)
        return proc.returncode == 0


class XzRunner(ProcessRunner):
    def __init__(self):
        super().__init__("xz", encoding=None)

    def compress(self, src, dest=None):
        proc = self("-z", "--check=crc32", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def decompress(self, src, dest=None):
        proc = self("-d", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def test(self, path):
        proc = self("-t", stdin=path, check=False)
        return proc.returncode == 0


class ZstdRunner(ProcessRunner):
    def __init__(self):
        super().__init__("zstd", encoding=None)

    def compress(self, src, dest=None):
        proc = self("-z", "-9", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def decompress(self, src, dest=None):
        proc = self("-d", stdin=src, stdout=dest)

        if dest is None:
            return proc.stdout
        else:
            return Path(dest)

    def test(self, path):
        proc = self("-t", stdin=path, check=False)
        return proc.returncode == 0


class MkimageRunner(ProcessRunner):
    def __init__(self):
        super().__init__("mkimage")


class VbutilKernelRunner(ProcessRunner):
    def __init__(self):
        super().__init__("futility", "vbutil_kernel")


class CgptRunner(ProcessRunner):
    def __init__(self):
        super().__init__("cgpt")

    def __call__(self, *args, **kwargs):
        proc = super().__call__(*args, **kwargs)
        lines = proc.stdout.splitlines()

        # Sometimes cgpt prints duplicate output.
        # https://bugs.chromium.org/p/chromium/issues/detail?id=463414
        mid = len(lines) // 2
        if lines[:mid] == lines[mid:]:
            proc.stdout = "\n".join(lines[:mid])

        return proc

    def _parse_subprocess_error(self, err):
        # Exits with nonzero status if it finds no partitions of
        # given type even if the disk has a valid partition table
        if not err.stderr:
            return None

        m = re.fullmatch(
            "ERROR: Can't open (.*): Permission denied\n",
            err.stderr,
        )
        if m:
            return PermissionError(
                "Couldn't open '{}', permission denied."
                .format(m.groups()[0])
            )

        return err


    def get_raw_attribute(self, disk, partno):
        proc = self("show", "-A", "-i", str(partno), str(disk))
        attribute = int(proc.stdout, 16)
        return attribute

    def set_raw_attribute(self, disk, partno, attribute):
        self("add", "-A", hex(attribute), "-i", str(partno), str(disk))

    def get_flags(self, disk, partno):
        attribute = self.get_raw_attribute(disk, partno)
        successful = (attribute >> 8) & 0x1
        tries = (attribute >> 4) & 0xF
        priority = (attribute >> 0) & 0xF

        return {
            "A": attribute,
            "S": successful,
            "P": priority,
            "T": tries,
        }

    def set_flags(self, disk, partno, A=None, S=None, P=None, T=None):
        flag_args = []
        if A is not None:
            flag_args += ["-A", str(int(A))]
        if S is not None:
            flag_args += ["-S", str(int(S))]
        if P is not None:
            flag_args += ["-P", str(int(P))]
        if T is not None:
            flag_args += ["-T", str(int(T))]

        self("add", *flag_args, "-i", str(partno), str(disk))

    def get_size(self, disk, partno):
        proc = self("show", "-s", "-i", str(partno), str(disk))
        blocks = int(proc.stdout)
        return blocks * 512

    def get_start(self, disk, partno):
        proc = self("show", "-b", "-i", str(partno), str(disk))
        blocks = int(proc.stdout)
        return blocks * 512

    def find_partitions(self, disk, type=None):
        if type is None:
            # cgpt find needs at least one of -t, -u, -l
            proc = self("show", "-q", "-n", disk)
            lines = proc.stdout.splitlines()
            partnos = [int(shlex.split(line)[2]) for line in lines]

        else:
            proc = self("find", "-n", "-t", type, disk)
            partnos = [int(n) for n in proc.stdout.splitlines()]

        return partnos

    def prioritize(self, disk, partno):
        self("prioritize", "-i", str(partno), str(disk))


class CrossystemRunner(ProcessRunner):
    def __init__(self):
        super().__init__("crossystem")

    def hwid(self):
        proc = self("hwid", check=False)

        if proc.returncode == 0:
            return proc.stdout
        else:
            return None

    def fwid(self):
        proc = self("fwid", check=False)

        if proc.returncode == 0:
            return proc.stdout
        else:
            return None


class FdtgetRunner(ProcessRunner):
    def __init__(self):
        super().__init__("fdtget")

    def get(self, dt_file, node='/', prop='', default=None, type=None):
        options = []

        if default is not None:
            options += ["--default", str(default)]

        if type == str:
            options += ["--type", "s"]
        elif type == int:
            options += ["--type", "i"]
        elif type == bytes:
            options += ["--type", 'bx']
        elif type is not None:
            options += ["--type", str(type)]

        proc = self(*options, str(dt_file), str(node), str(prop))

        # str.split takes too much memory
        def split(s):
            for m in re.finditer("(\S*)\s", s):
                yield m.group()

        if type in (None, int):
            try:
                data = [int(i) for i in split(proc.stdout)]
                return data[0] if len(data) == 1 else data
            except:
                pass

        if type in (None, bytes):
            try:
                # bytes.fromhex("0") doesn't work
                data = bytes(int(x, 16) for x in split(proc.stdout))
                return data
            except:
                pass

        data = str(proc.stdout).strip("\n")
        return data

    def properties(self, dt_file, node='/'):
        proc = self("--properties", str(dt_file), str(node), check=False)

        if proc.returncode == 0:
            return proc.stdout.splitlines()
        else:
            return []

    def subnodes(self, dt_file, node='/'):
        proc = self("--list", str(dt_file), str(node), check=False)
        nodes = proc.stdout.splitlines()

        if proc.returncode == 0:
            return proc.stdout.splitlines()
        else:
            return []


class FdtputRunner(ProcessRunner):
    def __init__(self):
        super().__init__("fdtput")

    def put(self, dt_file, node='/', prop='', value=None, type=None):
        if isinstance(value, list):
            values = value
        else:
            values = [value]

        value_args = []
        for value in values:
            if isinstance(value, str):
                value_args.append(value)
                if type is None:
                    type = str

            elif isinstance(value, bytes):
                value_args.extend(hex(c) for c in value)
                if type is None:
                    type = bytes

            elif isinstance(value, int):
                value_args.append(str(value))
                if type is None:
                    type = int

            else:
                value_args.append(str(value))

        options = []
        if type == str:
            options += ["--type", "s"]
        elif type == int:
            options += ["--type", "i"]
        elif type == bytes:
            options += ["--type", 'bx']
        elif type is not None:
            options += ["--type", str(type)]

        self(*options, str(dt_file), str(node), str(prop), *value_args)


class FileRunner(ProcessRunner):
    def __init__(self):
        super().__init__("file")

    def brief(self, path):
        proc = self("-b", path, check=False)

        if proc.returncode == 0:
            return proc.stdout.strip("\n")
        else:
            return None


gzip = GzipRunner()
lz4 = Lz4Runner()
lzma = LzmaRunner()
lzop = LzopRunner()
bzip2 = Bzip2Runner()
xz = XzRunner()
zstd = ZstdRunner()
mkimage = MkimageRunner()
vbutil_kernel = VbutilKernelRunner()
cgpt = CgptRunner()
crossystem = CrossystemRunner()
fdtget = FdtgetRunner()
fdtput = FdtputRunner()
file = FileRunner()
