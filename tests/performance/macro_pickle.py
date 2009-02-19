#! /usr/bin/python2.5

"""Script for testing the performance of pickling/unpickling.

This will pickle/unpickle long lists (several tens of thousands) of several
real-world representative objects.
"""

__author__ = "collinwinter@google.com (Collin Winter)"

# Python imports
import datetime
import gc
import optparse
import time

gc.disable()  # Minimize jitter.

DICT = {
    'ads_flags': 0L,
    'age': 18,
    'birthday': datetime.date(1980, 5, 7),
    'bulletin_count': 0L,
    'comment_count': 0L,
    'country': 'BR',
    'encrypted_id': 'G9urXXAJwjE',
    'favorite_count': 9L,
    'first_name': '',
    'flags': 412317970704L,
    'friend_count': 0L,
    'gender': 'm',
    'gender_for_display': 'Male',
    'id': 302935349L,
    'is_custom_profile_icon': 0L,
    'last_name': '',
    'locale_preference': 'pt_BR',
    'member': 0L,
    'tags': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    'profile_foo_id': 827119638L,
    'secure_encrypted_id': 'Z_xxx2dYx3t4YAdnmfgyKw',
    'session_number': 2L,
    'signup_id': '201-19225-223',
    'status': 'A',
    'theme': 1,
    'time_created': 1225237014L,
    'time_updated': 1233134493L,
    'unread_message_count': 0L,
    'user_group': '0',
    'username': 'collinwinter',
    'play_count': 9L,
    'view_count': 7L,
    'zip': ''}

TUPLE = ([265867233L, 265868503L, 265252341L, 265243910L, 265879514L,
          266219766L, 266021701L, 265843726L, 265592821L, 265246784L,
          265853180L, 45526486L, 265463699L, 265848143L, 265863062L,
          265392591L, 265877490L, 265823665L, 265828884L, 265753032L], 60)


def test_pickle(pickle, options, num_obj_copies):
    many_dicts = [dict(DICT) for _ in xrange(num_obj_copies)]
    many_tuples = [tuple(TUPLE) for _ in xrange(num_obj_copies)]

    # Warm-up runs.
    pickle.dumps(many_dicts, options.protocol)
    pickle.dumps(many_tuples, options.protocol)

    times = []
    for _ in xrange(options.num_runs):
        t0 = time.time()
        pickle.dumps(many_dicts, options.protocol)
        pickle.dumps(many_tuples, options.protocol)
        t1 = time.time()
        times.append(t1 - t0)
    return times


def test_unpickle(pickle, options, num_obj_copies):
    many_dicts = pickle.dumps([dict(DICT) for _ in xrange(num_obj_copies)],
                              options.protocol)
    many_tuples = pickle.dumps([tuple(TUPLE) for _ in xrange(num_obj_copies)],
                               options.protocol)

    # Warm-up runs.
    pickle.loads(many_dicts)
    pickle.loads(many_tuples)

    times = []
    for _ in xrange(options.num_runs):
        t0 = time.time()
        pickle.loads(many_dicts)
        pickle.loads(many_tuples)
        t1 = time.time()
        times.append(t1 - t0)
    return times


if __name__ == "__main__":
    parser = optparse.OptionParser(
        usage="%prog [pickle|unpickle] [options]",
        description=("Test the performance of pickling."))
    parser.add_option("-n", action="store", type="int", default=100,
                      dest="num_runs", help="Number of times to run the test.")
    parser.add_option("--use_cpickle", action="store_true",
                      help="Use the C version of pickle.")
    parser.add_option("--protocol", action="store", default=2, type="int",
                      help="Which protocol to use (0, 1, 2).")
    options, args = parser.parse_args()

    if "pickle" in args:
        benchmark = test_pickle
    elif "unpickle" in args:
        benchmark = test_unpickle
    else:
        raise RuntimeError("Need to specify either 'pickle' or 'unpickle'")

    if options.use_cpickle:
        num_obj_copies = 40000
        import cPickle as pickle
    else:
        num_obj_copies = 6000
        import pickle

    if options.protocol > 0:
        num_obj_copies *= 2  # Compensate for faster protocols.

    for t in benchmark(pickle, options, num_obj_copies):
        print t
