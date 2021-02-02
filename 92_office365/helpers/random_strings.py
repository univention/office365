import random
import string


def create_random_string_with_prefix(length, prefix=""):
    '''
    creates a simple random string with uppercase letters and numbers in
    a given length. These strings should be easily distinguishable from
    other objects a user may have created and thus allow a bulk-removal
    of all test data.
    '''
    return prefix + ''.join(random.choice(
        string.ascii_uppercase + string.digits) for _ in range(length))
