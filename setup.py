#! /usr/bin/env python3

import os
import re
import setuptools
import subprocess

root = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(root, 'README.rst'), encoding='utf-8') as f:
    readme = f.read()

if not os.path.exists("mkdepthcharge.1"):
    subprocess.run(
        ["rst2man", "mkdepthcharge.rst", "mkdepthcharge.1"],
        check=True,
    )

if not os.path.exists("depthchargectl.8"):
    subprocess.run(
        ["rst2man", "depthchargectl.rst", "depthchargectl.8"],
        check=True,
    )

def version(module):
    init_py = os.path.join(root, module, '__init__.py')
    pattern = re.compile('^__version__\s*=\s*(".*"|\'.*\')$')
    with open(init_py, encoding='utf-8') as f:
        for match in filter(bool, map(pattern.match, f)):
            return match.group(1)[1:-1]

setuptools.setup(
    name='depthcharge-tools',
    version=version("depthcharge_tools"),
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
)
