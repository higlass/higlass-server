import os
import os.path as op
import higlass_server.settings as hss

def get_datapath(relpath):
    parts = os.path.normpath(relpath).split(os.path.sep)
    subpath = os.path.join(*parts[1:])
    return op.join(hss.MEDIA_ROOT, subpath)
