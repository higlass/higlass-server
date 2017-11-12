import os.path as op
import higlass_server.settings as hss

def get_datapath(relpath):
    return op.join(hss.BASE_DIR, relpath)
