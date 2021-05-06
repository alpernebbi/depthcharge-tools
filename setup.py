#! /usr/bin/env python3

import pathlib
import setuptools

root = pathlib.Path(__file__).resolve().parent
readme = (root / 'README.rst').read_text()

setuptools.setup(
    name='depthcharge-tools',
    version='0.5.0',
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
            'mkdepthcharge=depthcharge_tools.mkdepthcharge:mkdepthcharge.main',
            'depthchargectl=depthcharge_tools.depthchargectl:depthchargectl.main',
        ],
    },
    keywords='ChromeOS ChromiumOS depthcharge vboot vbutil_kernel',
    packages=setuptools.find_packages(),
    package_data={
        "depthcharge_tools": ["config.ini", "boards.ini"],
    },
    install_requires=[''],
)
