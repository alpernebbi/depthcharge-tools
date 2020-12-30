#! /usr/bin/env python3

import configparser
import os
import pathlib
import re
import setuptools
import subprocess
import sys

def envdir(name, default):
    return pathlib.Path(os.environ.get(name, default))

PREFIX = envdir("PREFIX", sys.prefix)
BINDIR = envdir("BINDIR", PREFIX / "bin")
SBINDIR = envdir("SBINDIR", PREFIX / "sbin")
DATADIR = envdir("DATADIR", PREFIX / "share")
SYSCONFDIR = envdir("SYSCONFDIR", PREFIX / "etc")
LOCALSTATEDIR = envdir("LOCALSTATEDIR", PREFIX / "var")
LIBDIR = envdir("LIBDIR", PREFIX / "lib")
MANDIR = envdir("MANDIR", DATADIR / "man")
INITDDIR = envdir("INITDDIR", SYSCONFDIR / "init.d")
SYSTEMDDIR = envdir("SYSTEMDDIR", LIBDIR / "systemd/system")
BASHCOMPDIR = envdir("BASHCOMPDIR", DATADIR / "bash-completion/completions")
ZSHCOMPDIR = envdir("ZSHCOMPDIR", DATADIR / "zsh/site-functions")

root = pathlib.Path(__file__).resolve().parent
readme = (root / 'README.rst').read_text()

if not (root / "mkdepthcharge.1"):
    subprocess.run(
        ["rst2man", "mkdepthcharge.rst", "mkdepthcharge.1"],
        check=True,
    )

if not (root / "depthchargectl.8"):
    subprocess.run(
        ["rst2man", "depthchargectl.rst", "depthchargectl.8"],
        check=True,
    )

dirconfig = configparser.ConfigParser()
dirconfig.optionxform = str.upper
dirconfig["DEFAULT"].update(
    PREFIX=str(PREFIX),
    BINDIR=str(BINDIR),
    SBINDIR=str(SBINDIR),
    DATADIR=str(DATADIR),
    SYSCONFDIR=str(SYSCONFDIR),
    LOCALSTATEDIR=str(LOCALSTATEDIR),
    LIBDIR=str(LIBDIR),
    MANDIR=str(MANDIR),
    INITDDIR=str(INITDDIR),
    SYSTEMDDIR=str(SYSTEMDDIR),
    BASHCOMPDIR=str(BASHCOMPDIR),
    ZSHCOMPDIR=str(ZSHCOMPDIR),
)

dirs = root / "depthcharge_tools" / "dirs"
with dirs.open(mode="w") as f:
    dirconfig.write(f)

setuptools.setup(
    name='depthcharge-tools',
    version='0.5.0.dev0',
    description='Tools to manage the Chrome OS bootloader',
    long_description=readme,
    long_description_content_type="text/x-rst",
    url='https://github.com/alpernebbi/depthcharge-tools',
    author='Alper Nebi Yasak',
    author_email='alpernebiyasak@gmail.com',
    license='GPL2+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Boot',
    ],
    entry_points={
        'console_scripts': [
            'mkdepthcharge=depthcharge_tools.mkdepthcharge:mkdepthcharge._main',
            'depthchargectl=depthcharge_tools.depthchargectl:depthchargectl._main',
        ],
    },
    keywords='ChromeOS ChromiumOS depthcharge vboot vbutil_kernel',
    packages=setuptools.find_packages(),
    install_requires=[''],
    package_data={
        "depthcharge_tools": ["dirs"],
    },
    data_files=(
        (str(SYSCONFDIR / "depthcharge-tools"), [
            "conf/config",
            "conf/userdb",
        ]),
        (str(DATADIR / "depthcharge-tools"), ["conf/db"]),
        (str(MANDIR), ["mkdepthcharge.1", "depthchargectl.8"]),
        (str(SYSTEMDDIR), ["systemd/depthchargectl-set-good.service"]),
        (str(INITDDIR), ["init.d/depthchargectl-set-good"]),
        (str(BASHCOMPDIR), [
            "completions/_mkdepthcharge.bash",
            "completions/_depthchargectl.bash",
        ]),
        (str(ZSHCOMPDIR), [
            "completions/_mkdepthcharge.zsh",
            "completions/_depthchargectl.zsh",
        ]),
    ),
)
