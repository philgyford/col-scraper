import hashlib
import json
import os
import sqlite3

# Based on
# https://github.com/simonw/register-of-members-interests/blob/master/convert_xml_to_sqlite.py


DATA_DIRECTORY = 'data'

def init_db(filename):
    if os.path.exists(filename):
        return

    conn = sqlite3.connect(filename)
    conn.executescript(
        """
    CREATE TABLE members (
        id INTEGER NOT NULL,
        name VARCHAR(255) NOT NULL,
        role VARCHAR(50),
        party VARCHAR(50),
        ward VARCHAR(50),
        url VARCHAR(255),
        PRIMARY KEY (id)
    );
    CREATE TABLE interest_categories (
        id VARCHAR(8) NOT NULL,
        name VARCHAR(255),
        PRIMARY KEY (id)
    );
    CREATE TABLE interests (
        kind VARCHAR(10),
        name TEXT,
        category_id VARCHAR(8) REFERENCES categories(id),
        member_id INTEGER REFERENCES members(id)
    );
    CREATE TABLE gifts (
        name TEXT,
        date_str VARCHAR(50),
        date TEXT,
        member_id INTEGER REFERENCES members(id)
    );
    CREATE INDEX gifts_date ON gifts("date");
    CREATE INDEX gifts_member_id ON gifts("member_id");
    CREATE INDEX interests_category_id ON interests("category_id");
    CREATE INDEX interests_member_id ON interests("member_id");
    """
    )
    conn.close()


def insert_or_replace(cursor, table, record):
    pairs = record.items()
    columns = [p[0] for p in pairs]
    params = [p[1] for p in pairs]
    sql = "INSERT OR REPLACE INTO {table} ({column_list}) VALUES ({value_list});".format(
        table=table,
        column_list=", ".join(columns),
        value_list=", ".join(["?" for p in params]),
    )
    cursor.execute(sql, params)


def delete(cursor, table, key, val):
    """
    Delete everything from `table` where `key`=`val`.
    """
    sql = "DELETE FROM {table} WHERE {key}=?;".format(
        table=table,
        key=key
    )
    cursor.execute(sql, (val,))


def load_member(filepath, cursor):
    """
    Load all data for an indvidual member.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    load_member_info(data, cursor)

    load_interests(data, cursor)

    load_gifts(data, cursor)


def load_member_info(data, cursor):
    """
    Given the data from a member file, load the general member info from it.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    info = data['member']

    insert_or_replace(
        cursor,
        'members',
        {
            'id':       info['id'],
            'name':     info['name'],
            'role':     info['role'],
            'party':    info['party'],
            'ward':     info['ward'],
            'url':      info['url'],
        }
    )


def load_interests(data, cursor):
    """
    Given the data from a member file, load the interests.
    """
    # First, need to get all the categories, and insert/replace those.

    categories = []
    categories_by_name = {}

    for interest in data['interests']:
        if interest['name'] not in categories:
            categories.append(interest['name'])

    for category_name in categories:
        id = hashlib.sha1(
            category_name.encode("utf8")
        ).hexdigest()[
            :8
        ]
        insert_or_replace(
            cursor,
            'interest_categories',
            {
                'id':   id,
                'name': category_name,
            }
        )

        categories_by_name[category_name] = id

    # Now we can insert/replace all the interests.

    member_id = data['member']['id']

    # Nothing unique enough to be able to insert/replace, so start afresh:
    delete(cursor, 'interests', 'member_id', member_id)

    for interest in data['interests']:
        category_name = interest['name']
        category_id = categories_by_name[ category_name ]

        for item in interest['items']:
            for kind, name in item.items():
                if name != '':
                    insert_or_replace(
                        cursor,
                        'interests',
                        {
                            'member_id': member_id,
                            'category_id': category_id,
                            'kind': kind,
                            'name': name,
                        }
                    )


def load_gifts(data, cursor):
    """
    Given the data from a member file, load the gifts.
    """
    member_id = data['member']['id']

    # Nothing unique enough to be able to insert/replace, so start afresh:
    delete(cursor, 'gifts', 'member_id', member_id)

    for gift in data['gifts']:
        insert_or_replace(
            cursor,
            'gifts',
            {
                'name':         gift['name'],
                'date_str':     gift['date_str'],
                'date':         gift['date'],
                'member_id':    member_id,
            }
        )


if __name__ == "__main__":
    import sys

    dbfile = sys.argv[-1]
    assert dbfile.endswith(".db")
    init_db(dbfile)
    conn = sqlite3.connect(dbfile)
    c = conn.cursor()

    members_dir = os.path.join(DATA_DIRECTORY, 'members')

    for filename in os.listdir(members_dir):
        filepath = os.path.join(members_dir, filename)
        load_member(filepath, c)

    conn.commit()
    c.close()
