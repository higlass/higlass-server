import os


def is_subdir(path, directory):
    """Check if path is a sub directory of directory.
    """
    path = os.path.realpath(path)
    directory = os.path.realpath(directory)
    relative = os.path.relpath(path, directory)
    return not relative.startswith(os.pardir + os.sep)
