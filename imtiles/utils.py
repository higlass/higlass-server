import os
import sqlite3


def get_tileset_info(tileset):
    if not os.path.isfile(tileset):
        return {
            'error': 'Tileset info is not available!'
        }

    db = sqlite3.connect(tileset)

    res = db.execute('SELECT * FROM tileset_info').fetchone()

    o = {
        'tile_size': res[5],
        'max_zoom': res[6],
        'max_size': res[7],
    }

    try:
        o['width'] = res[8]
        o['height'] = res[9]
    except IndexError:
        pass

    try:
        o['dtype'] = res[10]
    except IndexError:
        pass

    return o
