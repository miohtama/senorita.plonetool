"""

    Some helper methods.

"""

import os


def read_template(fname):
    """
    Reads a local file as a string.

    A helper function to access some file templates we use.
    """
    path = os.path.join(os.path.dirname(__file__), fname)

    try:
        f = open(path, "rt")
        val = f.read()
        return val
    except:
        raise RuntimeError("Cannot access template file %s" % path)
