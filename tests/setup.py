#!/usr/bin/env python

"""Wrapper script for building all of Unladen Swallow's third-party tests.

This is equivalent to manually invoking setup.py in each lib/ directory.
"""

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import os
import os.path
import subprocess
import sys

# We skip psyco because Unladen Swallow's stdlib includes it (for now).
SKIP_LIBS = set(["psyco", ".svn"])


def SetupSubdir(subdir):
    """Run the setup.py command in the given subdir.

    Args:
        subdir: a directory relative to the current working directory where
            the setup.py command should be run.
    """
    current_dir = os.getcwd()
    os.chdir(subdir)
    try:
        retval = subprocess.call([sys.executable, "setup.py"] + sys.argv[1:])
        if retval:
          raise SystemExit()
    finally:
        os.chdir(current_dir)


def FindThirdPartyLibs(basedir):
    """Enumerate the subdirectories of the given base directory.

    Note that this will skip any .svn directories.

    Args:
        basedir: name of the directory for which to enumerate subdirectories.

    Yields:
        Directory names relative the current working directory.
    """
    for filename in os.listdir(basedir):
        entry = os.path.join(basedir, filename)
        if os.path.isdir(entry) and filename not in SKIP_LIBS:
            yield entry


if __name__ == "__main__":
    basedir = os.path.join(os.path.split(__file__)[0], "lib")
    for subdir in FindThirdPartyLibs(basedir):
        SetupSubdir(subdir)
