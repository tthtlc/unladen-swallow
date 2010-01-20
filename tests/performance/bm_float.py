#! /usr/bin/env python

"""
Semi-micro benchmark for floating point performance.

This is a Python implementation of a floating point benchmark originally on the
Factor language blog:
http://factor-language.blogspot.com/2009/08/performance-comparison-between-factor.html

Local changes:
- Reduced the number of points from 5000000 to 20000. This reduces individual
  iteration times, but we compensate by increasing the number of iterations.
"""

__author__ = "alex.gaynor@gmail.com (Alex Gaynor)"

# Python imports
import optparse
import time
from math import sin, cos, sqrt

# Local imports
import util


class Point(object):
    def __init__(self, i):
        self.x = x = sin(i)
        self.y = cos(i) * 3
        self.z = (x * x) / 2

    def normalize(self):
        norm = sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
        self.x = self.x / norm
        self.y = self.y / norm
        self.z = self.z / norm

    def maximize(self, other):
        self.x = self.x if self.x > other.x else other.x
        self.y = self.y if self.y > other.y else other.y
        self.z = self.z if self.z > other.z else other.z


def maximize(points):
    points = iter(points)
    cur = points.next()
    for p in points:
        cur.maximize(p)
    return cur


def benchmark():
    points = []
    for i in xrange(20000):
        points.append(Point(i))
    for p in points:
        p.normalize()
    maximize(points)


def test_float(count):
    times = []
    for _ in xrange(count):
        t0 = time.time()
        benchmark()
        t1 = time.time()
        times.append(t1 - t0)
    return times


if __name__ == "__main__":
    parser = optparse.OptionParser(
        usage="%prog [options]",
        description="Test the performance of various floating point ops")
    util.add_standard_options_to(parser)
    options, args = parser.parse_args()

    util.run_benchmark(options, options.num_runs, test_float)
