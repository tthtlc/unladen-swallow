#! /usr/bin/python2.5

"""Wrapper script for testing the performance of simple AI systems.

bm_ai.py runs the following little solvers:
    - N-Queens
    - alphametics (e.g., "SEND + MORE = MONEY")
"""

# Wanted by the alphametics solver.
from __future__ import division

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import optparse
import re
import string
import time


# Pure-Python implementation of itertools.permutations().
def permutations(iterable, r=None):
    """permutations(range(3), 2) --> (0,1) (0,2) (1,0) (1,2) (2,0) (2,1)"""
    pool = tuple(iterable)
    n = len(pool)
    if r is None:
        r = n
    indices = range(n)
    cycles = range(n-r+1, n+1)[::-1]
    yield tuple(pool[i] for i in indices[:r])
    while n:
        for i in reversed(range(r)):
            cycles[i] -= 1
            if cycles[i] == 0:
                indices[i:] = indices[i+1:] + indices[i:i+1]
                cycles[i] = n - i
            else:
                j = cycles[i]
                indices[i], indices[-j] = indices[-j], indices[i]
                yield tuple(pool[i] for i in indices[:r])
                break
        else:
            return


# From http://code.activestate.com/recipes/576615/
def alphametics(s):
    """Find solutions to alphametic equations.

    >>> solve('SEND + MORE == MONEY')
    9567 + 1085 == 10652
    """
    words = re.findall("[A-Za-z]+", s)
    chars = set("".join(words))         # Characters to be substituted.
    assert len(chars) <= 10             # There are only ten possible digits.
    firsts = set(w[0] for w in words)   # First letters of each of word.
    chars = "".join(firsts) + "".join(chars - firsts)
    n = len(firsts)                     # chars[:n] cannot be assigned zero.
    for perm in permutations("0123456789", len(chars)):
        if "0" not in perm[:n]:
            trans = string.maketrans(chars, "".join(perm))
            equation = s.translate(trans)
            if eval(equation):
                yield equation


# From http://code.activestate.com/recipes/576647/
def n_queens(queen_count):
    """N-Queens solver.

    Args:
        queen_count: the number of queens to solve for. This is also the
            board size.

    Yields:
        Solutions to the problem. Each yielded value is looks like
        (3, 8, 2, 1, 4, ..., 6) where each number is the column position for the
        queen, and the index into the tuple indicates the row.
    """
    cols = range(queen_count)
    for vec in permutations(cols):
        if (queen_count == len(set(vec[i]+i for i in cols))
                        == len(set(vec[i]-i for i in cols))):
            yield vec


def test_n_queens(iterations):
    # Warm-up run.
    list(n_queens(8))

    times = []
    for _ in xrange(iterations):
        t0 = time.time()
        list(n_queens(8))
        t1 = time.time()
        times.append(t1 - t0)
    return times


def test_alphametics(iterations):
    # This is a fairly simple equation. More interesting ones like
    # SEND + MORE = MONEY take forever to solve, though.
    equation = "EED + BE == CCCC"

    # Warm-up run.
    list(alphametics(equation))

    times = []
    for _ in xrange(iterations):
        t0 = time.time()
        list(alphametics(equation))
        t1 = time.time()
        times.append(t1 - t0)
    return times

if __name__ == "__main__":
    parser = optparse.OptionParser(
        usage="%prog [options]",
        description=("Test the performance of simple AI solvers."))
    parser.add_option("-n", action="store", type="int", default=100,
                      dest="num_runs", help="Number of times to run the test.")
    options, args = parser.parse_args()

    n_queens_times = test_n_queens(options.num_runs)
    alphametics_times = test_alphametics(options.num_runs)

    for x, y in zip(n_queens_times, alphametics_times):
        print x + y
