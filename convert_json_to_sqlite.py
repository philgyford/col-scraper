import hashlib
import json
import os
import sqlite3

# Based on
# https://github.com/simonw/register-of-members-interests/blob/master/convert_xml_to_sqlite.py


DATA_DIRECTORY = 'data'


wards_by_name = {}


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
        ward_id VARCHAR(8) REFERENCES wards(id),
        url VARCHAR(255),
        PRIMARY KEY (id)
    );
    CREATE TABLE wards(
        id VARCHAR(8) NOT NULL,
        name VARCHAR(50),
        PRIMARY KEY (id)
    );
    CREATE TABLE committees(
        id INTEGER NOT NULL,
        name VARCHAR(50),
        url VARCHAR(255),
        PRIMARY KEY (id)
    );
    CREATE TABLE committee_membership(
        committee_id INTEGER REFERENCES committees(id),
        member_id INTEGER REFERENCES members(id),
        role VARCHAR(50)
    );
    CREATE TABLE interest_categories (
        id VARCHAR(8) NOT NULL,
        name VARCHAR(255),
        PRIMARY KEY (id)
    );
    CREATE TABLE interests (
        kind VARCHAR(10),
        name TEXT,
        category_id VARCHAR(8) REFERENCES interest_categories(id),
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
    CREATE INDEX members_ward_id ON members("ward_id");
    CREATE INDEX committee_membership_committee_id ON committee_membership("committee_id");
    CREATE INDEX committee_membership_member_id ON committee_membership("member_id");
    """
    )
    conn.close()


def create_and_populate_fts(cursor):
    """
    Create full text search tables.
    """

    # Interests
    conn.executescript("""
        CREATE VIRTUAL TABLE "interests_fts"
        USING FTS4 (name, category, member, content="interests");
    """)
    conn.executescript("""
        INSERT INTO "interests_fts" (rowid, name, category, member)
        SELECT interests.rowid, interests.name, interest_categories.name, members.name
        FROM interests
        JOIN interest_categories ON interests.category_id = interest_categories.id
        JOIN members ON interests.member_id = members.id;
    """)

    # Gifts
    conn.executescript("""
        CREATE VIRTUAL TABLE "gifts_fts"
        USING FTS4 (name, member, content="gifts");
    """)
    conn.executescript("""
        INSERT INTO "gifts_fts" (rowid, name, member)
        SELECT gifts.rowid, gifts.name, members.name
        FROM gifts
        JOIN members ON gifts.member_id = members.id;
    """)


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


def load_wards(filepath, cursor):
    """
    Inserts/updates all the wards data, creating unique IDs, and adds them
    to the wards_by_name dict for future use.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    for ward in data['wards']:
        ward_name = ward['name']

        id = hashlib.sha1(
            ward_name.encode("utf8")
        ).hexdigest()[
            :8
        ]
        insert_or_replace(
            cursor,
            'wards',
            {
                'id':   id,
                'name': ward_name,
            }
        )

        wards_by_name[ward_name] = id


def load_committees(filepath, cursor):
    """
    Inserts/updates all the committees data.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    for committee in data['committees']:
        insert_or_replace(
            cursor,
            'committees',
            {
                'id':   committee['id'],
                'name': committee['name'],
                'url':  committee['url'],
            }
        )


def load_member(filepath, cursor):
    """
    Load all data for an indvidual member.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    load_member_info(data, cursor)

    load_member_committees(data, cursor)

    load_member_interests(data, cursor)

    load_member_gifts(data, cursor)


def load_member_info(data, cursor):
    """
    Given the data from a member file, load the general member info from it.
    """

    info = data['member']

    ward_id = wards_by_name[ info['ward'] ]

    insert_or_replace(
        cursor,
        'members',
        {
            'id':       info['id'],
            'name':     info['name'],
            'role':     info['role'],
            'party':    info['party'],
            'url':      info['url'],
            'ward_id':  ward_id,
        }
    )


def load_member_committees(data, cursor):
    """
    Given the data from a member file, load any committee data from it.
    We should already have the committees table populated.
    """

    for committee in data['committees']:
        insert_or_replace(
            cursor,
            'committee_membership',
            {
                'committee_id': committee['id'],
                'member_id':    data['member']['id'],
                'role':         committee['role'],
            }
        )


def load_member_interests(data, cursor):
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


def load_member_gifts(data, cursor):
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

    wards_filepath = os.path.join(DATA_DIRECTORY, 'wards.json')

    load_wards(wards_filepath, c)

    committees_filepath = os.path.join(DATA_DIRECTORY, 'committees.json')

    load_committees(committees_filepath, c)

    members_dir = os.path.join(DATA_DIRECTORY, 'members')

    for filename in os.listdir(members_dir):
        filepath = os.path.join(members_dir, filename)
        load_member(filepath, c)

    create_and_populate_fts(c)

    conn.commit()

    c.close()
