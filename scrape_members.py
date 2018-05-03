import argparse
import dateparser
import datetime
import json
import logging
import os
import re
import sys
import time
from urllib.parse import urlparse

from requests_html import HTMLSession


# Page listing all the members.
# The 'View members as a table' view.
MEMBERS_LIST_URL = 'http://democracy.cityoflondon.gov.uk/mgMemberIndex.aspx?VW=TABLE&PIC=1&FN='

# URL for a page showing a member's info.
# The {id} will be replaced with the member's ID.
MEMBERS_INFO_URL = 'http://democracy.cityoflondon.gov.uk/mgUserInfo.aspx?UID={id}'

# Output files
DATA_DIRECTORY = 'data'


# Get everything except the mgMemberIndex.aspx bit:
parsed_url = urlparse(MEMBERS_LIST_URL)
path = '/'.join( parsed_url[2].split('/')[:-1] )
BASE_URL = '{}://{}{}'.format(parsed_url[0], parsed_url[1], path)


logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

session = HTMLSession()


def scrape_all():
    """
    Fetch the page listing all Members.
    Save a JSON file with basic data about each Member.
    For each Member, fetch their interests and write a JSON file for that.
    """

    logger.debug("Requesting URL {}".format(MEMBERS_LIST_URL))

    r = session.get(MEMBERS_LIST_URL)

    rows = r.html.find('.mgStatsTable tbody tr')

    for row in rows:
        (photo_cell, member_cell, party_cell, ward_cell) = row.find('td')

        member_link =  member_cell.find('p', first=True).find('a', first=True)

        member_url = member_link.attrs['href']

        member_id = int(member_url.split('=')[-1])

        time.sleep(1)

        scrape_member(member_id)

    logger.info("Saved data for {} members".format(len(rows)))

    create_list_files()


def scrape_member(id):
    """
    Given the numeric ID of a member (e.g. 292), fetch their data and
    write a JSON file.

    Gets their basic info from the member's main page, then fetches their
    interests/gifts from their Register of Interests page.
    """

    logger.debug("Getting data for Member ID {}".format(id))

    url = MEMBERS_INFO_URL.replace('{id}', str(id))

    # What we'll end up saving to a file.
    member_data = {
        'meta': {
            'time_created': json_time_now(),
        },
        'member': {
            'id':       int(id),
            'url':      url,
            'name':     '',
            'role':     '',
            'ward':     '',
            'party':    '',
        },
        'interests':    {},
        'gifts':        {},
    }

    logger.debug("Requesting URL {}".format(url))

    r = session.get(url)


    # Find Member's Name and Role.

    name = r.html.find('.header-page-content h1', first=True).text

    if name.endswith(' (Alderman)'):
        name = name[:-11]
        role = 'Alderman'
    elif name.endswith(', Deputy'):
        role = 'Deputy'
        name = name[:-8]
    else:
        role = ''

    member_data['member']['name'] = name
    member_data['member']['role'] = role


    # Find Ward and Party

    sidebar_ps = r.html.find('.mgUserSideBar p')

    for p in sidebar_ps:
        # A p is like:
        # <p><span class="mgLabel">[label]:&nbsp;</span>[value]</p>

        label = p.find('.mgLabel', first=True).text

        if label.startswith('Ward:'):
            matches = re.search('Ward:(.*?)$', p.text)
            if matches:
                ward = matches.group(1).strip()
                member_data['member']['ward'] = ward

        elif label.startswith('Party:'):
            matches = re.search('Party:(.*?)$', p.text)
            if matches:
                party = matches.group(1).strip()
                member_data['member']['party'] = party


    # Get Register of interests.

    links = r.html.find('.mgUserBody .mgBulletList li')

    # Out of the links, find the URL for the interests, and use that.
    for li in links:
        if li.text == 'Register of interests':
            interests_url = li.find('a', first=True).attrs['href']

            interests_url = make_absolute( interests_url )

            interests_data = scrape_members_interests(id, interests_url)

            member_data['interests'] = interests_data['interests']
            member_data['gifts'] = interests_data['gifts']


    # Done. Write all the data.

    filename = os.path.join(DATA_DIRECTORY, 'members', '{}.json'.format(id))

    with open(filename, 'w') as f:
        json.dump(member_data, f, indent=2, ensure_ascii=False)


def scrape_members_interests(id, url):
    """
    Fetch the page about a Member's interests and gifts and return the data.

    id is the numeric ID of the member (e.g. 292).
    url is the URL of the page containing the Member's interests.
        e.g. 'http://democracy.cityoflondon.gov.uk/mgRofI.aspx?UID=292&FID=-1&HPID=505555082'

    Returned dict is like:

        {
            'interests': [ ... ],
            'gifts': [ ... ],
        }
    """

    logger.debug("Requesting URL {}".format(url))

    interests = []
    gifts = []

    # We'll ignore rows where both columns are one of these:
    empty_values = ['nil', 'none', 'n/a', '-']

    r = session.get(url)

    tables = r.html.find('.mgInterestsTable')

    for table in tables:
        # Might get changed to 'gifts':
        kind = 'interests'

        name = table.find('caption', first=True).text

        if name == 'Gifts of Hospitality':
            kind = 'gifts'

        # Will have a dict per populated row in the table:
        items = []

        for row in table.find('tr'):
            cells = row.find('td')

            if cells:
                # First column's cell, e.g. 'Member' or 'Hospitality received...'
                a = cells[0].text
                # Tidy NIL etc values to empty string:
                if a.lower() in empty_values:
                    a = ''

                # Second column's cell, e.g. 'Spouse...' or 'Date received'
                # Some tables only have a 'Member' column,
                # e.g. ID 292
                if len(cells) > 1:
                    b = cells[1].text
                    if b.lower() in empty_values:
                        b = ''
                else:
                    b = ''

                if a or b:
                    if kind == 'gifts':
                        date_str = b
                        # Try to make an actual datetime from the date string.
                        if re.search(r'20\d\d', date_str):
                            # If there's no year, dateparser will use the current
                            # year, which isn't necessarily right, so skip those.
                            d = dateparser.parse(date_str,
                                                settings={'DATE_ORDER': 'DMY'})
                            if d:
                                # Don't need a datetime, just a date.
                                d = d.strftime('%Y-%m-%d')
                        else:
                            d = None

                        gifts.append({
                            'name': a,
                            'date_str': date_str,
                            'date': d,
                        })
                    else:
                        items.append({
                            'member': a,
                            'partner': b,
                        })

        if kind == 'interests':
            interests.append({
                'name': name,
                'items': items,
            })

    return {
        'interests': interests,
        'gifts': gifts,
    }


def create_list_files():
    """
    Go through all the JSON member files and create two extra files:

        * members.json, listing all the members we have JSON files for.
        * wards.json, listing the wards we have members for.
    """

    ward_names = []

    members = []

    dir_path = os.path.join(DATA_DIRECTORY, 'members')

    for filename in os.listdir(dir_path):
        filepath = os.path.join(dir_path, filename)

        with open(filepath, 'r') as f:
            member = json.load(f)

            members.append({
                'id': member['member']['id'],
                'name': member['member']['name'],
            })

            ward = member['member']['ward']

            if ward != '' and ward not in ward_names:
                ward_names.append(ward)


    members_data = {
        'members': members,
    }
    members_file = os.path.join(DATA_DIRECTORY, 'members.json')

    with open(members_file, 'w') as f:
        json.dump(members_data, f, indent=2, ensure_ascii=False)


    wards_data = {
        'wards': [{'name': w} for w in sorted(ward_names)],
    }

    wards_file = os.path.join(DATA_DIRECTORY, 'wards.json')

    with open(wards_file, 'w') as f:
        json.dump(wards_data, f, indent=2, ensure_ascii=False)


def make_absolute(url):
    """
    If url is not absolute on the CoL website, make it so.
    """
    if not url.startswith('http'):
        url = '{}/{}'.format(BASE_URL, url)

    return url


def json_time_now():
    """
    Return the current UTC datetime as a string suitable for putting in JSON.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='''Scrapes data about Members' from the City of London website.
            Supply the ID of a single Member to only fetch their data.
            Otherwise, data about all Members will be fetched.''' )

    parser.add_argument(
                '-i', '--id',
                help="ID of a single Member to fetch",
                required=False)

    parser.add_argument(
                '-v', '--verbose',
                action='count',
                help="Verbose output",
                required=False)

    create_list_files()
    exit()
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.id:
        logger.info("Scraping a single Members' data")
        logger.info("ID: {}".format(args.id))
        scrape_member(args.id)
    else:
        logger.info("Scraping all Members' data")
        scrape_all()
