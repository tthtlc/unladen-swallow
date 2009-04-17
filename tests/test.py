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

# We skip psyco because it doesn't build against Unladen Swallow trunk.
# It's still useful for testing against vanilla builds, though.
# TODO(collinwinter): add test integration for Spitfire.
SKIP_LIBS = set(["psyco", ".svn", "spitfire"])


@contextlib.contextmanager
def ChangeDir(new_cwd):
    former_cwd = os.getcwd()
    os.chdir(new_cwd)
    yield
    os.chdir(former_cwd)


def CallAndCaptureOutput(command, env=None):
    """Run the given command, capturing stdout and stderr.

    Args:
        command: the command to run as a list, one argument per element.
        env: optional; dict of environment variables to set.

    Returns:
        The captured stdout + stderr as a string.

    Raises:
        RuntimeError: if the command failed. The value of the exception will
        be the error message from the command.
    """
    subproc = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               env=env)
    result, err = subproc.communicate()
    print result + err,
    return result + err


def DefaultPassCheck(command, env=None):
    """Run a test command and check whether it passed.

    This works for most test suites we run, but not all. Pass/fail is
    determined by whether the final line of output starts with OK.

    Args:
        command: the command to run as a list, one argument per element.
        env: optional; dict of environment variables to set.

    Returns:
        True if the test passed, False otherwise.
    """
    output = CallAndCaptureOutput(command, env)
    lines = output.splitlines()
    if not lines:
        return False
    return lines[-1].startswith("OK")


### Wrappers for the third-party modules we don't want to break go here. ###

def Test2to3():
    return DefaultPassCheck([sys.executable, "-E", "test.py"])

def TestCheetah():
    path = ":".join([os.environ["PATH"], os.path.dirname(sys.executable)])
    with ChangeDir(os.path.join("src", "Tests")):
        return DefaultPassCheck([sys.executable, "-E", "Test.py"],
                                env={"PATH": path})

def TestDjango():
    py_path = os.path.join("..", "..", "correctness")
    test_runner = os.path.join("tests", "runtests.py")
    return DefaultPassCheck([sys.executable, test_runner, "-v1",
                             "--settings=django_data.settings"],
                            env={"PYTHONPATH": py_path})

def TestMercurial():
    with ChangeDir("tests"):
        output = CallAndCaptureOutput([sys.executable, "-E", "run-tests.py"])
        lines = output.splitlines()
        return lines[-1].endswith(" 0 failed.")

def TestNose():
    return DefaultPassCheck([sys.executable, "-E", "selftest.py"])

def TestNumpy():
    # Numpy refuses to be imported from the source directory.
    with ChangeDir(".."):
        return DefaultPassCheck([sys.executable, "-E", "-c",
                                 "import numpy; numpy.test()"])

def TestPyxml():
    with ChangeDir("test"):
        output = CallAndCaptureOutput([sys.executable, "-E", "regrtest.py"])
        lines = output.splitlines()
        return lines[-1].endswith("OK.")


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
    tests_passed = {}
    for dirname, subdir in FindThirdPartyLibs(basedir):
        test_name = dirname.capitalize()
        test_func = globals()["Test" + test_name]

        print "Testing", test_name
        current_dir = os.getcwd()
        os.chdir(subdir)
        try:
            tests_passed[test_name] = test_func()
        finally:
            os.chdir(current_dir)

    if all(tests_passed.values()):
        print "All OK"
    else:
        failed = [test for (test, passed) in tests_passed.items() if not passed]
        print "FAILED:", failed
        sys.exit(1)
