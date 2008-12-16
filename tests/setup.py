#!/usr/bin/env python

"""Wrapper script for all of Unladen Swallow's third-party tests.

This is equivalent to manually invoking setup.py in each lib/ directory.
"""

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import os
import os.path
import subprocess
import sys


def SetupSubdir(subdir):
    """Run the setup.py command in the given subdir.

    Args:
        subdir: a directory relative to the current working directory where
            the setup.py command should be run.
    """
    current_dir = os.getcwd()
    os.chdir(subdir)
    try:
        retval = subprocess.call([sys.executable] + sys.argv)
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
        if os.path.isdir(entry) and filename != ".svn":
            yield entry


if __name__ == "__main__":
    for subdir in FindThirdPartyLibs("lib"):
        SetupSubdir(subdir)
