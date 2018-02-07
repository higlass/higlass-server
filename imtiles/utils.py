import os
import sqlite3


def get_features(db_file_path, zoom, x_from, x_to, y_from, y_to):
    '''
    Retrieve them features from the database.

    Parameters
    ----------
    db_file_path: str
        The filename of the sqlite db file
    zoom: int
        The zoom level
    x_from: foat
        The start of the longitude
    x_to: foat
        The end of the longitude
    y_from: foat
        The start of the latitude
    y_to: foat
        The end of the latitude

    Returns
    -------
    rows: list
        Rows of the database matching the query
    '''

    conn = sqlite3.connect(db_file_path)
    c = conn.cursor()

    query = '''
    SELECT
        fromX, toX, fromY, toY, chrOffset, importance, fields, uid
    FROM
        intervals,position_index
    WHERE
        intervals.id=position_index.id AND
        zoomLevel <= ? AND
        rToX >= ? AND
        rFromX <= ? AND
        rToY >= ? AND
        rFromY <= ?
    '''

    return c.execute(query, (zoom, x_from, x_to, y_from, y_to)).fetchall()


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
