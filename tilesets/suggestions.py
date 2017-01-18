import sqlite3

def get_gene_suggestions(db_file, text):
    '''
    Get a list of autocomplete suggestions for genes containing
    the text.

    Args:

    db_file (string): The filename for the SQLite file containing gene annotations
    text (string): The text to be included in the suggestions

    Returns:

    suggestions (list): A list of dictionaries containing the suggestions:
        e.g. ([{'txStart': 10, 'txEnd': 20, 'score': 15, 'geneName': 'XV4'}])
    '''
    con = sqlite3.connect(db_file)
    c = con.cursor()

    query = """
        SELECT importance, chrOffset, fields FROM intervals
        WHERE fields LIKE '%{}%'
        ORDER BY importance DESC
        LIMIT 10
        """.format(text)

    rows = c.execute(query).fetchall()

    to_return = []
    for (importance, chrOffset, fields) in rows:
        field_parts = fields.split('\t')
        to_return += [{
                      'chr': field_parts[0],
                      'txStart': int(field_parts[1]),
                      'txEnd': int(field_parts[2]),
                      'score': importance,
                      'geneName': field_parts[3]}]

    c.execute(query)



    return to_return
