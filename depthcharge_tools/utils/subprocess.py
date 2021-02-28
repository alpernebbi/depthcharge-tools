#! /usr/bin/env python3

import contextlib
import logging
import pathlib
import subprocess

logger = logging.getLogger(__name__)


class ProcessRunner:
    def __init__(self, *args_prefix, **kwargs_defaults):
        self.args_prefix = args_prefix
        self.kwargs_defaults = {
            'stdin': subprocess.PIPE,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'encoding': "utf-8",
            'check': True,
        }
        self.kwargs_defaults.update(kwargs_defaults)

    def __call__(self, *args_suffix, **kwargs_overrides):
        args = (*self.args_prefix, *args_suffix)
        kwargs = {**self.kwargs_defaults, **kwargs_overrides}

        with contextlib.ExitStack() as ctx:
            stdin = kwargs.get("stdin")
            if isinstance(stdin, str):
                stdin = pathlib.Path(stdin)
            if isinstance(stdin, pathlib.Path):
                kwargs["stdin"] = ctx.enter_context(stdin.open("r"))

            stdout = kwargs.get("stdout")
            if isinstance(stdout, str):
                stdout = pathlib.Path(stdout)
            if isinstance(stdout, pathlib.Path):
                kwargs["stdout"] = ctx.enter_context(stdout.open("x"))

            stderr = kwargs.get("stderr")
            if isinstance(stderr, str):
                stderr = pathlib.Path(stderr)
            if isinstance(stderr, pathlib.Path):
                kwargs["stderr"] = ctx.enter_context(stderr.open("x"))

            return subprocess.run(args, **kwargs)


class GzipRunner(ProcessRunner):
    def __init__(self):
        super().__init__("gzip")

    def compress(self, src, dest):
        return self("-c", "-6", stdin=src, stdout=dest)

    def decompress(self, src, dest):
        return self("-c", "-d", stdin=src, stdout=dest)

    def test(self, path):
        return self("-t", stdin=path, check=False)


class Lz4Runner(ProcessRunner):
    def __init__(self):
        super().__init__("lz4")

    def compress(self, src, dest):
        return self("-z", "-9", stdin=src, stdout=dest)

    def decompress(self, src, dest):
        return self("-d", stdin=src, stdout=dest)

    def test(self, path):
        return self("-t", stdin=path, check=False)


class LzmaRunner(ProcessRunner):
    def __init__(self):
        super().__init__("lzma")

    def compress(self, src, dest):
        return self("-z", stdin=src, stdout=dest)

    def decompress(self, src, dest):
        return self("-d", stdin=src, stdout=dest)

    def test(self, path):
        return self("-t", stdin=path, check=False)


class MkimageRunner(ProcessRunner):
    def __init__(self):
        super().__init__("mkimage")


class VbutilKernelRunner(ProcessRunner):
    def __init__(self):
        super().__init__("futility", "vbutil_kernel")


class CgptRunner(ProcessRunner):
    def __init__(self):
        super().__init__("sudo", "cgpt")

    def __call__(self, *args, **kwargs):
        proc = super().__call__(*args, **kwargs)
        lines = proc.stdout.splitlines()

        # Sometimes cgpt prints duplicate output.
        # https://bugs.chromium.org/p/chromium/issues/detail?id=463414
        mid = len(lines) // 2
        if lines[:mid] == lines[mid:]:
            proc.stdout = "\n".join(lines[:mid])

        return proc


class BlockdevRunner(ProcessRunner):
    def __init__(self):
        super().__init__("sudo", "blockdev")


class CrossystemRunner(ProcessRunner):
    def __init__(self):
        super().__init__("sudo", "crossystem")


class FdtgetRunner(ProcessRunner):
    def __init__(self):
        super().__init__("fdtget")


gzip = GzipRunner()
lz4 = Lz4Runner()
lzma = LzmaRunner()
mkimage = MkimageRunner()
vbutil_kernel = VbutilKernelRunner()
cgpt = CgptRunner()
blockdev = BlockdevRunner()
crossystem = CrossystemRunner()
fdtget = FdtgetRunner()
