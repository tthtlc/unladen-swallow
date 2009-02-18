#! /usr/bin/python2.5

"""Wrapper script for comparing the performance of two python implementations.

"""

from __future__ import division, with_statement

__author__ = "jyasskin@google.com (Jeffrey Yasskin)"

import contextlib
import logging
import math
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


# A table of 95% confidence intervals for a two-tailed t distribution, as a
# function of the degrees of freedom. For larger degrees of freedom, we
# approximate. While this may look less elegant than simply calculating the
# critical value, those calculations suck. Look at
# http://www.math.unb.ca/~knight/utility/t-table.htm if you need more values.
T_DIST_95_CONF_LEVELS = [0, 12.706, 4.303, 3.182, 2.776,
                         2.571, 2.447, 2.365, 2.306, 2.262,
                         2.228, 2.201, 2.179, 2.160, 2.145,
                         2.131, 2.120, 2.110, 2.101, 2.093,
                         2.086, 2.080, 2.074, 2.069, 2.064,
                         2.060, 2.056, 2.052, 2.048, 2.045,
                         2.042]


def TDist95ConfLevel(df):
    """Approximate the 95% confidence interval for Student's T distribution.

    Given the degrees of freedom, returns an approximation to the 95%
    confidence interval for the Student's T distribution.

    Args:
        df: An integer, the number of degrees of freedom.

    Returns:
        A float.
    """
    df = int(round(df))
    highest_table_df = len(T_DIST_95_CONF_LEVELS)
    if df >= 200: return 1.960
    if df >= 100: return 1.984
    if df >= 80: return 1.990
    if df >= 60: return 2.000
    if df >= 50: return 2.009
    if df >= 40: return 2.021
    if df >= highest_table_df:
        return T_DIST_95_CONF_LEVELS[highest_table_df - 1]
    return T_DIST_95_CONF_LEVELS[df]


def PooledSampleVariance(sample1, sample2):
    """Find the pooled sample variance for two samples.

    Args:
        sample1: one sample.
        sample2: the other sample.

    Returns:
        Pooled sample variance, as a float.
    """
    deg_freedom = len(sample1) + len(sample2) - 2
    mean1 = avg(sample1)
    squares1 = ((x - mean1) ** 2 for x in sample1)
    mean2 = avg(sample2)
    squares2 = ((x - mean2) ** 2 for x in sample2)

    return (sum(squares1) + sum(squares2)) / float(deg_freedom)


def TScore(sample1, sample2):
    """Calculate a t-test score for the difference between two samples.

    Args:
        sample1: one sample.
        sample2: the other sample.

    Returns:
        The t-test score, as a float.
    """
    assert len(sample1) == len(sample2)
    error = PooledSampleVariance(sample1, sample2) / len(sample1)
    return (avg(sample1) - avg(sample2)) / math.sqrt(error * 2)


def IsSignificant(sample1, sample2):
    """Determine whether two samples differ significantly.

    This uses a Student's two-sample, two-tailed t-test with alpha=0.95.

    Args:
        sample1: one sample.
        sample2: the other sample.

    Returns:
        (significant, t_score) where significant is a bool indicating whether
        the two samples differ significantly; t_score is the score from the
        two-sample T test.
    """
    deg_freedom = len(sample1) + len(sample2) - 2
    critical_value = TDist95ConfLevel(deg_freedom)
    t_score = TScore(sample1, sample2)
    return (t_score >= critical_value, t_score)


@contextlib.contextmanager
def ChangeDir(new_cwd):
    former_cwd = os.getcwd()
    os.chdir(new_cwd)
    yield
    os.chdir(former_cwd)


def RemovePycs():
    subprocess.check_call(["find", ".", "-name", "*.py[co]",
                           "-exec", "rm", "-f", "{}", ";"])


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
            RemovePycs()
            subprocess.check_call(LogCall([changed_python, "-E", "-O",
                                           PYBENCH_PATH,
                                           "-w", warp,
                                           "-f", changed_pybench,
                                           ]), stdout=dev_null,
                                           env=PYBENCH_ENV)
            RemovePycs()
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
    FAST_TARGET = Relative("lib/2to3/lib2to3/refactor.py")
    TWO_TO_THREE_PROG = Relative("lib/2to3/2to3")
    TWO_TO_THREE_DIR = Relative("lib/2to3")
    TWO_TO_THREE_ENV = {"PYTHONPATH": ""}

    if options.fast:
        target = FAST_TARGET
    else:
        target = TWO_TO_THREE_DIR

    with open("/dev/null", "wb") as dev_null:
        RemovePycs()
        # Warm up the cache and .pyc files.
        subprocess.check_call(LogCall([python, "-E", "-O",
                                       TWO_TO_THREE_PROG,
                                       "-f", "all",
                                       target]),
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
                                           target]),
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
        return CompareMultipleRuns(base_times, changed_times, options)


def CompareMultipleRuns(base_times, changed_times, options):
    """Compare multiple control vs experiment runs of the same benchmark.

    Args:
        base_times: iterable of float times (control).
        changed_times: iterable of float times (experiment).
        options: optparse.Values instance.

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

    t_msg = "Not significant"
    significant, t_score = IsSignificant(base_times, changed_times)
    if significant:
        t_msg = "Significant (t=%f, a=0.95)" % t_score

    return (("Min: %(min_base).3f -> %(min_changed).3f:" +
             " %(delta_min)s\n" +
             "Avg: %(avg_base).3f -> %(avg_changed).3f:" +
             " %(delta_avg)s\n" + t_msg)
             % locals())


def CallAndCaptureOutput(command, env={}):
    """Run the given command, capturing stdout.

    Args:
        command: the command to run as a list, one argument per element.
        env: optional; environment variables to set.

    Returns:
        The captured stdout as a string.

    Raises:
        RuntimeError: if the command failed. The value of the exception will
        be the error message from the command.
    """
    subproc = subprocess.Popen(LogCall(command),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               env=env)
    result, err = subproc.communicate()
    if subproc.returncode != 0:
        raise RuntimeError("Benchmark died: " + err)
    return result


def MeasureDjango(python, options):
    DJANGO_DIR = Relative("lib/django")
    TEST_PROG = Relative("performance/macro_django.py")

    django_env = {"PYTHONPATH": DJANGO_DIR}

    trials = 50
    if options.rigorous:
        trials = 100
    elif options.fast:
        trials = 5

    RemovePycs()
    command = [python, "-O", TEST_PROG, "-n", trials]
    result = CallAndCaptureOutput(command, django_env)
    return [float(line) for line in result.splitlines()]


def BM_Django(base_python, changed_python, options):
    try:
        changed_times = MeasureDjango(changed_python, options)
        base_times = MeasureDjango(base_python, options)
    except subprocess.CalledProcessError, e:
        return str(e)

    return CompareMultipleRuns(base_times, changed_times, options)


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

    trials = 50
    if options.rigorous:
        trials = 100
    elif options.fast:
        trials = 5

    RemovePycs()
    command = [python, "-O", TEST_PROG, "-n", trials] + extra_args
    result = CallAndCaptureOutput(command, env)
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

    return CompareMultipleRuns(base_times, changed_times, options)


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

    return CompareMultipleRuns(base_times, changed_times, options)


def MeasurePickle(python, options, extra_args):
    """Test the performance of Python's pickle implementations.

    Args:
        python: path to the Python binary.
        options: optparse.Values instance.
        extra_args: list of arguments to append to the command line.

    Returns:
        List of floats, each the time it took to run the pickle test once.
    """
    TEST_PROG = Relative("performance/macro_pickle.py")
    CLEAN_ENV = {"PYTHONPATH": ""}

    trials = 50
    if options.rigorous:
        trials = 100
    elif options.fast:
        trials = 5

    RemovePycs()
    command = [python, "-O", TEST_PROG, "-n", trials] + extra_args
    result = CallAndCaptureOutput(command, env=CLEAN_ENV)
    return [float(line) for line in result.splitlines()]


def _PickleBenchmark(base_python, changed_python, options, extra_args):
    """Test the performance of Python's pickle implementations.

    Args:
        base_python: path to the reference Python binary.
        changed_python: path to the experimental Python binary.
        options: optparse.Values instance.
        extra_args: list of arguments to append to the command line.

    Returns:
        Summary of whether the experiemental Python is better/worse than the
        baseline.
    """
    try:
        changed_times = MeasurePickle(changed_python, options, extra_args)
        base_times = MeasurePickle(base_python, options, extra_args)
    except subprocess.CalledProcessError, e:
        return str(e)
    return CompareMultipleRuns(base_times, changed_times, options)


def BM_Pickle(base_python, changed_python, options):
    args = ["--use_cpickle", "pickle"]
    return _PickleBenchmark(base_python, changed_python, options, args)


def BM_Unpickle(base_python, changed_python, options):
    args = ["--use_cpickle", "unpickle"]
    return _PickleBenchmark(base_python, changed_python, options, args)


def BM_SlowPickle(base_python, changed_python, options):
    return _PickleBenchmark(base_python, changed_python, options, ["pickle"])


def BM_SlowUnpickle(base_python, changed_python, options):
    return _PickleBenchmark(base_python, changed_python, options, ["unpickle"])


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
