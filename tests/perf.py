#! /usr/bin/python2.5

"""Wrapper script for comparing the performance of two python implementations.

"""

from __future__ import division, with_statement

__author__ = "jyasskin@google.com (Jeffrey Yasskin)"

import contextlib
import logging
import optparse
import os
import os.path
import platform
import re
import resource
import shutil
import subprocess
import sys
import tempfile


info = logging.info


def avg(seq):
    return sum(seq) / len(seq)


@contextlib.contextmanager
def ChangeDir(new_cwd):
    former_cwd = os.getcwd()
    os.chdir(new_cwd)
    yield
    os.chdir(former_cwd)


def Relative(path):
    return os.path.join(os.path.dirname(sys.argv[0]), path)


def LogCall(command):
    command = map(str, command)
    info("Running %s", " ".join(command))
    return command


def GetChildUserTime():
    return resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime


@contextlib.contextmanager
def TemporaryFilename(prefix):
    fd, name = tempfile.mkstemp(prefix=prefix)
    os.close(fd)
    try:
        yield name
    finally:
        os.remove(name)


def TimeDelta(old, new):
    delta = ((new - old) / new) * 100
    if delta > 0:
        return "%.2f%% slower" % delta
    else:
        return "%.2f%% faster" % -delta


_PY_BENCH_TOTALS_LINE = re.compile("""
    Totals:\s+(?P<min_base>\d+)ms\s+
    (?P<min_changed>\d+)ms\s+
    \S+\s+  # Percent change, which we re-compute
    (?P<avg_base>\d+)ms\s+
    (?P<avg_changed>\d+)ms\s+
    \S+  # Second percent change, also re-computed
    """, re.X)
def MungePyBenchTotals(line):
    m = _PY_BENCH_TOTALS_LINE.search(line)
    if m:
        min_base, min_changed, avg_base, avg_changed = map(float, m.group(
            "min_base", "min_changed", "avg_base", "avg_changed"))
        delta_min = TimeDelta(min_base, min_changed)
        delta_avg = TimeDelta(avg_base, avg_changed)
        return (("Min: %(min_base)d -> %(min_changed)d: %(delta_min)s\n" +
                 "Avg: %(avg_base)d -> %(avg_changed)d: %(delta_avg)s")
                % locals())
    return line


def BM_PyBench(base_python, changed_python, options):
    warp = "10"
    if options.rigorous:
        warp = "1"
    if options.fast:
        warp = "100"

    PYBENCH_PATH = Relative("performance/pybench/pybench.py")
    PYBENCH_ENV = {"PYTHONPATH": ""}

    try:
        with contextlib.nested(open("/dev/null", "wb"),
                               TemporaryFilename(prefix="baseline."),
                               TemporaryFilename(prefix="changed.")
                               ) as (dev_null, base_pybench, changed_pybench):
            subprocess.check_call(LogCall([changed_python, "-E", "-O",
                                           PYBENCH_PATH,
                                           "-w", warp,
                                           "-f", changed_pybench,
                                           ]), stdout=dev_null,
                                           env=PYBENCH_ENV)
            subprocess.check_call(LogCall([base_python, "-E", "-O",
                                           PYBENCH_PATH,
                                           "-w", warp,
                                           "-f", base_pybench,
                                           ]), stdout=dev_null,
                                           env=PYBENCH_ENV)
            comparer = subprocess.Popen([base_python, "-E",
                                         PYBENCH_PATH,
                                         "-s", base_pybench,
                                         "-c", changed_pybench,
                                         ], stdout=subprocess.PIPE,
                                         env=PYBENCH_ENV)
            result, err = comparer.communicate()
            if comparer.returncode != 0:
                return "pybench died: " + err
    except subprocess.CalledProcessError, e:
        return str(e)

    if options.verbose:
        return result
    else:
        for line in result.splitlines():
            if line.startswith("Totals:"):
                return MungePyBenchTotals(line)
        # The format's wrong...
        return result


def Measure2to3(python, options):
    TWO_TO_THREE_PROG = Relative("lib/2to3/2to3")
    TWO_TO_THREE_DIR = Relative("lib/2to3")
    TWO_TO_THREE_ENV = {"PYTHONPATH": ""}

    if options.fast:
        warmup_target = TWO_TO_THREE_PROG
    else:
        warmup_target = TWO_TO_THREE_DIR

    with open("/dev/null", "wb") as dev_null:
        # Warm up the cache and .pyc files.
        subprocess.check_call(LogCall([python, "-E", "-O",
                                       TWO_TO_THREE_PROG,
                                       "-f", "all",
                                       warmup_target]),
                              stdout=dev_null, stderr=dev_null,
                              env=TWO_TO_THREE_ENV)
        if options.rigorous:
            trials = 5
        else:
            trials = 1
        times = []
        for _ in range(trials):
            start_time = GetChildUserTime()
            subprocess.check_call(LogCall([python, "-E", "-O",
                                           TWO_TO_THREE_PROG,
                                           "-f", "all",
                                           TWO_TO_THREE_DIR]),
                                  stdout=dev_null, stderr=dev_null,
                                  env=TWO_TO_THREE_ENV)
            end_time = GetChildUserTime()
            elapsed = end_time - start_time
            assert elapsed != 0
            times.append(elapsed)

    return times


def BM_2to3(base_python, changed_python, options):
    try:
        changed_times = sorted(Measure2to3(changed_python, options))
        base_times = sorted(Measure2to3(base_python, options))
    except subprocess.CalledProcessError, e:
        return str(e)

    assert len(base_times) == len(changed_times)

    if len(base_times) == 1:
        base_time = base_times[0]
        changed_time = changed_times[0]
        time_delta = TimeDelta(base_time, changed_time)
        return ("%(base_time).2f -> %(changed_time).2f: %(time_delta)s"
                % locals())
    else:
        return CompareMultipleRuns(base_times, changed_times)


def CompareMultipleRuns(base_times, changed_times):
    """Compare multiple control vs experiment runs of the same benchmark.

    Args:
        base_times: iterable of float times (control).
        changed_times: iterable of float times (experiment).

    Returns:
        A string summarizing the difference between the runs, suitable for
        human consumption.
    """
    assert len(base_times) == len(changed_times)
    base_times = sorted(base_times)
    changed_times = sorted(changed_times)

    min_base, min_changed = base_times[0], changed_times[0]
    avg_base, avg_changed = avg(base_times), avg(changed_times)
    delta_min = TimeDelta(min_base, min_changed)
    delta_avg = TimeDelta(avg_base, avg_changed)
    return (("Min: %(min_base).2f -> %(min_changed).2f:" +
             " %(delta_min)s\n" +
             "Avg: %(avg_base).2f -> %(avg_changed).2f:" +
             " %(delta_avg)s")
             % locals())


def MeasureDjango(python, options):
    DJANGO_DIR = Relative("lib/django")
    TEST_PROG = Relative("performance/macro_django.py")

    django_env = {"PYTHONPATH": DJANGO_DIR}

    with open("/dev/null", "wb") as dev_null:
        trials = 50
        if options.rigorous:
            trials = 100
        elif options.fast:
            trials = 5

        command = [python, "-O", TEST_PROG, "-n", trials]
        django = subprocess.Popen(LogCall(command),
                                  stdout=subprocess.PIPE, stderr=dev_null,
                                  env=django_env)
        result, err = django.communicate()
        if django.returncode != 0:
            return "Django test died: " + err
        return [float(line) for line in result.splitlines()]


def BM_Django(base_python, changed_python, options):
    try:
        changed_times = MeasureDjango(changed_python, options)
        base_times = MeasureDjango(base_python, options)
    except subprocess.CalledProcessError, e:
        return str(e)

    return CompareMultipleRuns(base_times, changed_times)


def ComesWithPsyco(python):
    """Determine whether the given Python binary already has Psyco.

    If the answer is no, we should build it (see BuildPsyco()).

    Args:
        python: path to the Python binary.

    Returns:
        True if we can "import psyco" with the given Python, False if not.
    """
    try:
        with open("/dev/null", "wb") as dev_null:
            subprocess.check_call([python, "-E", "-c", "import psyco"],
                                  stdout=dev_null, stderr=dev_null)
        return True
    except subprocess.CalledProcessError:
        return False


def BuildPsyco(python):
    """Build Psyco against the given Python binary.

    Args:
        python: path to the Python binary.

    Returns:
        Path to Psyco's build directory. Putting this on your PYTHONPATH will
        make "import psyco" work.
    """
    PSYCO_SRC_DIR = Relative("lib/psyco")

    info("Building Psyco for %s", python)
    psyco_build_dir = tempfile.mkdtemp()
    abs_python = os.path.abspath(python)
    with ChangeDir(PSYCO_SRC_DIR):
        subprocess.check_call(LogCall([abs_python, "setup.py", "build",
                                       "--build-lib=" + psyco_build_dir]))
    return psyco_build_dir


def MeasureSpitfire(python, options, env={}, extra_args=[]):
    """Use Spitfire to test a Python binary's performance.

    Args:
        python: path to the Python binary to test.
        options: optparse.Values instance.
        env: optional; dict of environment variables to pass to Python.
        extra_args: optional; list of arguments to append to the Python
            command.

    Returns:
        List of floats, each the time it took to run the Spitfire test once.
    """
    TEST_PROG = Relative("performance/macro_spitfire.py")

    with open("/dev/null", "wb") as dev_null:
        trials = 50
        if options.rigorous:
            trials = 100
        elif options.fast:
            trials = 5

        command = [python, "-O", TEST_PROG, "-n", trials] + extra_args
        spitfire = subprocess.Popen(LogCall(command),
                                    stdout=subprocess.PIPE, stderr=dev_null,
                                    env=env)
        result, err = spitfire.communicate()
        if spitfire.returncode != 0:
            return "Spitfire test died: " + err
        return [float(line) for line in result.splitlines()]


def MeasureSpitfireWithPsyco(python, options):
    """Use Spitfire to measure Python's performance.

    Args:
        python: path to the Python binary.
        options: optparse.Values instance.

    Returns:
        List of floats, each the time it took to run the Spitfire test once.
    """
    SPITFIRE_DIR = Relative("lib/spitfire")

    psyco_dir = ""
    if not ComesWithPsyco(python):
        psyco_dir = BuildPsyco(python)

    env_dirs = filter(bool, [SPITFIRE_DIR, psyco_dir])
    spitfire_env = {"PYTHONPATH": ":".join(env_dirs)}

    try:
        return MeasureSpitfire(python, options, spitfire_env)
    finally:
        try:
            shutil.rmtree(psyco_dir)
        except OSError:
            pass


def BM_Spitfire(base_python, changed_python, options):
    try:
        changed_times = MeasureSpitfireWithPsyco(changed_python, options)
        base_times = MeasureSpitfireWithPsyco(base_python, options)
    except subprocess.CalledProcessError, e:
        return str(e)

    return CompareMultipleRuns(base_times, changed_times)


def BM_SlowSpitfire(base_python, changed_python, options):
    extra_args = ["--disable_psyco"]
    spitfire_env = {"PYTHONPATH": Relative("lib/spitfire")}
    try:
        changed_times = MeasureSpitfire(changed_python, options,
                                        spitfire_env, extra_args)
        base_times = MeasureSpitfire(base_python, options,
                                     spitfire_env, extra_args)
    except subprocess.CalledProcessError, e:
        return str(e)

    return CompareMultipleRuns(base_times, changed_times)


def ParseBenchmarksOption(options, legal_benchmarks):
    """Parses and verifies the --benchmarks option so ShouldRun can use it.

    Sets options.positive_benchmarks and options.negative_benchmarks.
    """
    benchmarks = options.benchmarks.split(",")
    options.positive_benchmarks = set(
        bm.lower() for bm in benchmarks if bm and bm[0] != "-")
    options.negative_benchmarks = set(
        bm[1:].lower() for bm in benchmarks if bm and bm[0] == "-")

    legal_benchmarks = set(name.lower() for (name, func) in legal_benchmarks)
    for bm in options.positive_benchmarks | options.negative_benchmarks:
        if bm not in legal_benchmarks:
            logging.warning("No benchmark named %s", bm)


def ShouldRun(benchmark, options):
    """Returns true if the options indicate that we should run 'benchmark'."""
    benchmark = benchmark.lower()
    if benchmark in options.negative_benchmarks:
        return False
    if options.positive_benchmarks:
        return benchmark in options.positive_benchmarks
    return True


if __name__ == "__main__":
    benchmarks = [(name[3:], func)
                  for name, func in sorted(globals().iteritems())
                  if name.startswith("BM_")]

    parser = optparse.OptionParser(
        usage="%prog [options] baseline_python changed_python",
        description=("Compares the performance of baseline_python with" +
                     " changed_python and prints a report."))
    parser.add_option("-r", "--rigorous", action="store_true",
                      help=("Spend longer running tests to get more" +
                            " accurate results"))
    parser.add_option("-f", "--fast", action="store_true",
                      help=("Get rough answers quickly"))
    parser.add_option("-v", "--verbose", action="store_true",
                      help=("Print more output"))
    parser.add_option("-b", "--benchmarks", metavar="BM_LIST", default="",
                      help=("Comma-separated list of benchmarks to run.  Can" +
                            " contain both positive and negative arguments:" +
                            "  --benchmarks=run_this,also_this,-not_this.  If" +
                            " there are no positive arguments, we'll run all" +
                            " benchmarks except the negative arguments. " +
                            " Otherwise we run only the positive arguments. " +
                            " Valid benchmarks are: " +
                            ", ".join(name for (name, func) in benchmarks)))

    options, args = parser.parse_args()
    if len(args) != 2:
        parser.error("incorrect number of arguments")
    base, changed = args

    logging.basicConfig(level=logging.INFO)

    ParseBenchmarksOption(options, benchmarks)

    results = []
    for name, func in benchmarks:
        if ShouldRun(name, options):
            print "Running %s..." % name
            results.append((name, func(base, changed, options)))

    print
    print "Report on %s" % " ".join(platform.uname())
    for name, result in results:
        print
        print name + ":"
        print result
