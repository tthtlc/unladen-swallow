#! /usr/bin/python2.5

"""Wrapper script for comparing the performance of two python implementations.

"""

from __future__ import division, with_statement

__author__ = "jyasskin@google.com (Jeffrey Yasskin)"

import contextlib
import logging
import optparse
import os
import platform
import re
import resource
import subprocess
import sys
import tempfile


info = logging.info


def Relative(path):
    return os.path.join(os.path.dirname(sys.argv[0]), path)


def LogCall(command):
    info("Running %s", " ".join(command))
    return command


def GetChildUserTime():
    return resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime


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

    with contextlib.nested(open("/dev/null", "wb"),
                           tempfile.NamedTemporaryFile(prefix="baseline."),
                           tempfile.NamedTemporaryFile(prefix="changed.")
                           ) as (dev_null, base_pybench, changed_pybench):
        subprocess.check_call(LogCall([base_python, "-O",
                                       PYBENCH_PATH,
                                       "-w", warp,
                                       "-f", base_pybench.name,
                                       ]), stdout=dev_null)
        subprocess.check_call(LogCall([changed_python, "-O",
                                       PYBENCH_PATH,
                                       "-w", warp,
                                       "-f", changed_pybench.name,
                                       ]), stdout=dev_null)
        comparer = subprocess.Popen([base_python,
                                     PYBENCH_PATH,
                                     "-s", base_pybench.name,
                                     "-c", changed_pybench.name,
                                     ], stdout=subprocess.PIPE)
        result, _ = comparer.communicate()

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

    if options.fast:
        warmup_target = TWO_TO_THREE_PROG
    else:
        warmup_target = TWO_TO_THREE_DIR

    with open("/dev/null", "wb") as dev_null:
        # Warm up the cache and .pyc files.
        subprocess.check_call(LogCall([python, "-O",
                                       TWO_TO_THREE_PROG,
                                       "-f", "all",
                                       warmup_target]),
                              stdout=dev_null, stderr=dev_null)
        if options.rigorous:
            trials = 5
        else:
            trials = 1
        times = []
        for _ in range(trials):
            start_time = GetChildUserTime()
            subprocess.check_call(LogCall([python, "-O",
                                           TWO_TO_THREE_PROG,
                                           "-f", "all",
                                           TWO_TO_THREE_DIR]),
                                  stdout=dev_null, stderr=dev_null)
            end_time = GetChildUserTime()
            elapsed = end_time - start_time
            assert elapsed != 0
            times.append(elapsed)

    return times


def avg(seq):
    return sum(seq) / len(seq)


def BM_2to3(base_python, changed_python, options):
    with open("/dev/null", "wb") as dev_null:
        base_times = sorted(Measure2to3(base_python, options))
        changed_times = sorted(Measure2to3(changed_python, options))
        assert len(base_times) == len(changed_times)

        if len(base_times) == 1:
            base_time = base_times[0]
            changed_time = changed_times[0]
            time_delta = TimeDelta(base_time, changed_time)
            return ("%(base_time).2f -> %(changed_time).2f: %(time_delta)s"
                    % locals())
        else:
            min_base, min_changed = base_times[0], changed_times[0]
            avg_base, avg_changed = avg(base_times), avg(changed_times)
            delta_min = TimeDelta(min_base, min_changed)
            delta_avg = TimeDelta(avg_base, avg_changed)
            return (("Min: %(min_base).2f -> %(min_changed).2f:" +
                     " %(delta_min)s\n" +
                     "Avg: %(avg_base).2f -> %(avg_changed).2f:" +
                     " %(delta_avg)s")
                    % locals())


if __name__ == "__main__":
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

    options, args = parser.parse_args()
    if len(args) != 2:
        parser.error("incorrect number of arguments")
    base, changed = args

    logging.basicConfig(level=logging.INFO)

    benchmarks = [(name[3:], func)
                  for name, func in sorted(globals().iteritems())
                  if name.startswith("BM_")]

    results = []
    for name, func in benchmarks:
        print "Running %s..." % name
        results.append((name, func(base, changed, options)))

    print
    print "Report on %s" % " ".join(platform.uname())
    for name, result in results:
        print
        print name + ":"
        print result
