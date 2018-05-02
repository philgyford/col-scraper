import argparse
import dateparser
import datetime
import json
import logging
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

members = []


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

        # Get name and URL

        member_link =  member_cell.find('p', first=True).find('a', first=True)

        url = make_absolute( member_link.attrs['href'] )

        name = member_link.text

        role = 'Common Councillor'

        if name.endswith(' (Alderman)'):
            name = name[:11]
            role = 'Alderman'
        elif name.endswith(', Deputy'):
            name = name[:8]

        # Get ID from URL

        id = int(url.split('=')[-1])

        # Get party and ward

        party = party_cell.text

        ward = ward_cell.text

        members.append({
            'id': id,
            'name': name,
            'url': url,
            'role': role,
            'party': party,
            'ward': ward,
        })

        time.sleep(1)

        scrape_member(id)

    filename = '{}/members.json'.format(DATA_DIRECTORY)

    data = {
        'meta': {
            'time_created': json_time_now(),
        },
        'members': members,
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Saved data for {} members".format(len(members)))


def scrape_member(id):
    """
    Given the numeric ID of a member (e.g. 292), fetch their interests and
    write a JSON file.

    To get the URL for the interests, we first have to get the page of basic
    info about the Member and find the URL on that.
    """

    url = MEMBERS_INFO_URL.replace('{id}', str(id))

    logger.debug("Getting data for Member ID {}".format(id))
    logger.debug("Requesting URL {}".format(url))

    r = session.get(url)

    links = r.html.find('.mgUserBody .mgBulletList li')

    # Find the URL for the interests, and use that.
    for li in links:
        if li.text == 'Register of interests':
            interests_url = li.find('a', first=True).attrs['href']

            interests_url = make_absolute( interests_url )

            scrape_members_interests(id, interests_url)


def scrape_members_interests(id, url):
    """
    Fetch the page about a Member's interests and write to a JSON file.

    id is the numeric ID of the member (e.g. 292).
    url is the URL of the page containing the Member's interests.
        e.g. 'http://democracy.cityoflondon.gov.uk/mgRofI.aspx?UID=292&FID=-1&HPID=505555082'
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

    filename = '{}/members/{}.json'.format(DATA_DIRECTORY, id)

    data = {
        'meta': {
            'time_created': json_time_now(),
        },
        'member': {
            'id': id,
        },
        'interests': interests,
        'gifts': gifts,
    }

    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
                '-v', '--verbosity',
                action='count',
                help="Verbose output",
                required=False)

    args = parser.parse_args()

    if args.verbosity:
        logger.setLevel(logging.DEBUG)

    if args.id:
        logger.info("Scraping a single Members' data")
        logger.info("ID: {}".format(args.id))
        scrape_member(args.id)
    else:
        logger.info("Scraping all Members' data")
        scrape_all()
