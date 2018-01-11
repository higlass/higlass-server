import os
import sqlite3


def get_tileset_info(tileset):
    if not os.path.isfile(tileset):
        return {
            'error': 'Tileset info is not available!'
        }

    db = sqlite3.connect(tileset)

    (
        _, _, _, _, _,
        tile_size, max_zoom, max_height, max_width, dtype
    ) = db.execute('SELECT * FROM tileset_info').fetchone()

    return {
        'tile_size': tile_size,
        'max_width': max_width,
        'max_height': max_height,
        'max_zoom': max_zoom
    }
