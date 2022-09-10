#!/usr/bin/env python3
#
# This file is part of django-ca (https://github.com/mathiasertl/django-ca).
#
# django-ca is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# django-ca is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-ca.  If not,
# see <http://www.gnu.org/licenses/>.

"""Script that scans a directory tree and outputs any file that should not be in a Docker image.

The script will output all unwanted files and exit with status code 1 if any are found.
"""

import argparse
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description="Check that Docker image does not contain any unwanted files.")
parser.add_argument(
    "--ignore-devscripts",
    action="store_true",
    default=False,
    help="Ignore the devscripts/ folder (used when building the image).",
)
parser.add_argument("-p", "--path", default="/usr/src/django-ca", help="Path to check (default: %(default)s.")
args = parser.parse_args()

path = Path(args.path)
patterns = [
    # Files maybe generated by building, testing, ...
    "*.crl",
    "*.csr",
    "*.key",
    "*.pem",
    "*.log",
    # generated files:
    "*.pyc",
    "__pycache__",
    # included files that really should not be in the image:
    "dev.py",
    "docs",
    "test",
    "tests",
    # project configuration files:
    "MANIFEST*",
    "pyproject.toml",
    "requirements*",
    "setup.cfg",
    "setup.py",
    "tox.ini",
]
if not args.ignore_devscripts:
    patterns.append("devscripts")
unwanted = []
for pattern in patterns:
    unwanted += path.rglob(pattern)

if unwanted:
    print("Image contains unwanted files:")
    for path in sorted(unwanted):
        print(str(path))

    sys.exit(1)