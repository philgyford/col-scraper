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


    # Get committees.
    member_data['committees'] = extract_member_committees(r)

    # Get interests and gifts.
    interests_data = extract_member_interests(r, id)
    member_data['interests'] = interests_data['interests']
    member_data['gifts'] = interests_data['gifts']

    # Done. Write all the data.

    filename = os.path.join(DATA_DIRECTORY, 'members', '{}.json'.format(id))

    with open(filename, 'w') as f:
        json.dump(member_data, f, indent=2, ensure_ascii=False)


def extract_member_committees(r):
    """
    Get a member's committees from `r`, the requested page.

    Returns a list.
    """

    committees = []

    # Committees are listed in a ul.mgBulletList which isn't unique.
    # So we go through all of those and look at the first item in each list.
    # If that item has a link to a committee page, we know this is the
    # correct list.

    for ul in r.html.find('.mgBulletList'):
        try:
            items = ul.find('li')
            first_href = items[0].find('a', first=True).attrs['href']
            if first_href.startswith('mgCommitteeDetails'):
                # This is the Committee list.

                for item in items:
                    committee_name = item.text
                    committee_role = ''

                    # The name might end in one of these, which we need to
                    # remove and use as the member's role for that committee:
                    roles = ['Chairman',
                            'Deputy Chairman',
                            'Ex-Officio Member',
                            'Vice-Chair',]

                    for role in roles:
                        if committee_name.endswith(' ({})'.format(role)):
                            trim = -(len(role) + 3)
                            committee_name = committee_name[:trim]
                            committee_role = role
                            break

                    # The URL is like 'mgCommitteeDetails.aspx?ID=220':
                    committee_url = item.find('a', first=True).attrs['href']
                    committee_id = int(committee_url.split('=')[-1])

                    committees.append({
                        'id': committee_id,
                        'name': committee_name,
                        'role': committee_role,
                    })
        except:
            logger.debug("No Committees found.")

    return committees


def extract_member_interests(r, member_id):
    """
    Get a member's interests and gifts from `r`, the requested page.
    """

    return_data = {
        'interests':    {},
        'gifts':        [],
    }

    links = r.html.find('.mgUserBody .mgBulletList li')

    # Out of the links, find the URL for the interests, and use that.
    for li in links:
        if li.text == 'Register of interests':
            interests_url = li.find('a', first=True).attrs['href']

            interests_url = make_absolute( interests_url )

            interests_data = scrape_members_interests(member_id, interests_url)

            return_data['interests'] = interests_data['interests']
            return_data['gifts'] = interests_data['gifts']

    return return_data


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
        * committees.json, listing all the committees members are on.
    """

    ward_names = []

    members = []

    committees = []

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

            for committee in member['committees']:
                committees.append({
                    'id': committee['id'],
                    'name': committee['name'],
                })

    members_data = {
        'members': members,
    }

    write_json_file('members.json', members_data)

    wards_data = {
        # Turn list of names into list of dicts:
        'wards': [{'name': w} for w in sorted(ward_names)],
    }

    write_json_file('wards.json', wards_data)

    committees_data = {
        # Make the committees dict unique:
        'committees': [dict(y) for y in set(tuple(x.items()) for x in committees)]
    }

    write_json_file('committees.json', committees_data)



def write_json_file(filename, data):
    """
    Writes `data` to `filename` within the DATA_DIRECTORY.
    Adds a ['meta']['time_created'] value to `data`.
    """

    if 'meta' not in data:
        data['meta'] = {}

    data['meta']['time_created'] = json_time_now()

    filepath = os.path.join(DATA_DIRECTORY, filename)

    with open(filepath, 'w') as f:
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
                '-v', '--verbose',
                action='count',
                help="Verbose output",
                required=False)

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
