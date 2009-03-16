#!/usr/bin/env python

"""Wrapper script for running all of Unladen Swallow's third-party tests.

This is equivalent to manually invoking the tests for each third-party app/lib.
Note that this script is intended to be invoked after setup.py install (certain)
tests depend on it.
"""

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import contextlib
import os
import os.path
import subprocess
import sys

# We skip psyco because Unladen Swallow's stdlib includes it (for now).
SKIP_LIBS = set(["psyco", ".svn"])


@contextlib.contextmanager
def ChangeDir(new_cwd):
    former_cwd = os.getcwd()
    os.chdir(new_cwd)
    yield
    os.chdir(former_cwd)


### Wrappers for the third-party modules we don't want to break go here. ###

def Test2to3():
    return subprocess.call([sys.executable] + ["test.py"])

def TestCheetah():
    path = ":".join([os.environ["PATH"], os.path.dirname(sys.executable)])
    with ChangeDir(os.path.join("src", "Tests")):
        return subprocess.call([sys.executable] + ["Test.py"],
                               env={"PATH": path})

def TestDjango():
    pass

def TestPyxml():
    with ChangeDir("test"):
        return subprocess.call([sys.executable] + ["regrtest.py"])

def TestSpitfire():
    pass


### Utility code ###

def FindThirdPartyLibs(basedir):
    """Enumerate the subdirectories of the given base directory.

    Note that this will skip any .svn directories.

    Args:
        basedir: name of the directory for which to enumerate subdirectories.

    Yields:
        (dirname, relpath) 2-tuples, where dirname is the name of the
        subdirectory, and relpath is the relative path to the subdirectory from
        the current working directory.
    """
    for filename in os.listdir(basedir):
        entry = os.path.join(basedir, filename)
        if os.path.isdir(entry) and filename not in SKIP_LIBS:
            yield (filename, entry)


if __name__ == "__main__":
    basedir = os.path.join(os.path.split(__file__)[0], "lib")
    for dirname, subdir in FindThirdPartyLibs(basedir):
        test_func = globals()["Test" + dirname.capitalize()]

        current_dir = os.getcwd()
        os.chdir(subdir)
        try:
            test_func()
        finally:
            os.chdir(current_dir)
