#! /usr/bin/python2.5

"""Tests for utility functions in perf.py."""

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import unittest

# Local imports
import perf


class Object(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# There's no particular significance to these values.
DATA1 = [89.2, 78.2, 89.3, 88.3, 87.3, 90.1, 95.2, 94.3, 78.3, 89.3]
DATA2 = [79.3, 78.3, 85.3, 79.3, 88.9, 91.2, 87.2, 89.2, 93.3, 79.9]


class TestStatsFunctions(unittest.TestCase):

    def testPooledSampleVariance(self):
        result = perf.PooledSampleVariance(DATA1, DATA2)
        self.assertAlmostEqual(result, 31.782, places=3)

        # Should be the same result, regardless of the input order.
        result = perf.PooledSampleVariance(DATA2, DATA1)
        self.assertAlmostEqual(result, 31.782, places=3)

    def testTScore(self):
        self.assertAlmostEqual(perf.TScore(DATA1, DATA2), 1.0947, places=4)
        self.assertAlmostEqual(perf.TScore(DATA2, DATA1), -1.0947, places=4)

    def testIsSignificant(self):
        (significant, _) = perf.IsSignificant(DATA1, DATA2)
        self.assertFalse(significant)
        (significant, _) = perf.IsSignificant(DATA2, DATA1)
        self.assertFalse(significant)

        inflated = [x * 10 for x in DATA1]
        (significant, _) = perf.IsSignificant(inflated, DATA1)
        self.assertTrue(significant)
        (significant, _) = perf.IsSignificant(DATA1, inflated)
        self.assertTrue(significant)


class TestMisc(unittest.TestCase):

    def testShouldRun(self):
        # perf.py, no -b option.
        options = Object(negative_benchmarks=[], positive_benchmarks=[])
        self.assertTrue(perf.ShouldRun("2to3", options))
        self.assertTrue(perf.ShouldRun("spitfire", options))
        self.assertFalse(perf.ShouldRun("pybench", options))

        # perf.py -b 2to3
        options.positive_benchmarks = ["2to3"]
        self.assertTrue(perf.ShouldRun("2to3", options))
        self.assertFalse(perf.ShouldRun("spitfire", options))
        self.assertFalse(perf.ShouldRun("pybench", options))

        # perf.py -b 2to3,pybench
        options.positive_benchmarks = ["2to3", "pybench"]
        options.negative_benchmarks = []
        self.assertTrue(perf.ShouldRun("2to3", options))
        self.assertFalse(perf.ShouldRun("spitfire", options))
        self.assertTrue(perf.ShouldRun("pybench", options))

        # perf.py -b -2to3
        options.positive_benchmarks = []
        options.negative_benchmarks = ["2to3"]
        self.assertFalse(perf.ShouldRun("2to3", options))
        self.assertTrue(perf.ShouldRun("spitfire", options))
        self.assertFalse(perf.ShouldRun("pybench", options))


if __name__ == "__main__":
    unittest.main()
