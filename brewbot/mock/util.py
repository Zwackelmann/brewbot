import os
from brewbot.util import flatten

def list_files_with_prefix(prefix):
    if isinstance(prefix, list):
        return flatten([list_files_with_prefix(p) for p in prefix])

    prefix = os.path.abspath(prefix)
    suffixes = ["a", "b"]
    return [(prefix + s) for s in suffixes]
