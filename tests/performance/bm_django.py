#! /usr/bin/python2.5

"""Wrapper script for testing the performance of the Django template system.

This is intended to support Unladen Swallow's perf.py

This will have Django generate a 100x100 table as many times as you
specify (via the -n flag). The raw times to generate the template will be
dumped to stdout. This is more convenient for Unladen Swallow's uses: it
allows us to keep all our stats in perf.py.
"""

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import optparse
import time

# Django imports
from django.conf import settings
settings.configure()
from django.template import Context, Template


DJANGO_TMPL = Template("""<table>
{% for row in table %}
<tr>{% for col in row %}<td>{{ col|escape }}</td>{% endfor %}</tr>
{% endfor %}
</table>
""")

def test_django(count):
    table = [xrange(150) for _ in xrange(150)]
    context = Context({"table": table})

    # Warm up Django.
    DJANGO_TMPL.render(context)
    DJANGO_TMPL.render(context)

    times = []
    for _ in xrange(count):
        t0 = time.time()
        data = DJANGO_TMPL.render(context)
        t1 = time.time()
        times.append(t1 - t0)
    return times


if __name__ == "__main__":
    parser = optparse.OptionParser(
        usage="%prog [options]",
        description=("Test the performance of Django templates."))
    parser.add_option("-n", action="store", type="int", default=100,
                      dest="num_runs", help="Number of times to run the test.")
    parser.add_option("--profile", action="store_true",
                      help="Run the benchmark through cProfile.")
    parser.add_option("--profile_sort", action="store", type="str",
                      default="time", help="Column to sort cProfile output by.")
    options, args = parser.parse_args()

    if options.profile:
        import cProfile
        prof = cProfile.Profile()
        prof.runcall(test_django, options.num_runs)
        prof.print_stats(sort=options.profile_sort)
    else:
        for t in test_django(options.num_runs):
            print t
