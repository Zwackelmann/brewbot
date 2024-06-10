import os
from functools import reduce


def path_has_prefix(path, prefix):
    prefix = os.path.abspath(prefix)
    path = os.path.abspath(path)

    for prefix_dir, filename_prefix in [(prefix, None), (os.path.dirname(prefix), os.path.basename(prefix))]:
        if os.path.commonpath([prefix_dir, path]) == prefix_dir and \
                (filename_prefix is None or os.path.basename(path).startswith(filename_prefix)):
            return True

    return False


def list_files_with_prefix(prefix):
    if isinstance(prefix, list):
        return flatten([list_files_with_prefix(p) for p in prefix])

    prefix = os.path.abspath(prefix)
    res = []
    for prefix_dir, filename_prefix in [(prefix, None), (os.path.dirname(prefix), os.path.basename(prefix))]:
        if os.path.isdir(prefix_dir):
            files = os.listdir(prefix_dir)
            if filename_prefix is not None:
                files = [os.path.join(prefix_dir, f) for f in files if f.startswith(filename_prefix)]
            res.extend(files)

    return res


def validate_int(i, valid_interval=(None, None), varname=None):
    if valid_interval[0] is None:
        valid_interval = (-float('inf'), valid_interval[1])

    if valid_interval[1] is None:
        valid_interval = (valid_interval[0], float('inf'))

    if varname is None:
        varname = 'variable'

    try:
        _i = int(i)
    except ValueError:
        _i = None

    if _i is None:
        raise ValueError(f'value for {varname} is a valid integer: {i}')

    if not valid_interval[0] <= _i <= valid_interval[1]:
        raise ValueError(f'{varname} must be in [{valid_interval[0]}, {valid_interval[1]}]')

    return _i


def flatten(li):
    return reduce(list.__add__, li)


class _ConfMeta(type):
    def __init__(cls, *_, **__):
        super().__init__(cls)

    def conf_dict(cls):
        raise NotImplemented()

    def get(cls, key, default=None):
        val = cls.conf_dict().get(key)
        return val if val is not None else default
