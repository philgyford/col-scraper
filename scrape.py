import argparse
import json
import sys
import logging
from urllib.parse import urlparse

from requests_html import HTMLSession

# Page listing all the members.
# The 'View members as a table' view.
MEMBERS_LIST_URL = 'http://democracy.cityoflondon.gov.uk/mgMemberIndex.aspx?VW=TABLE&PIC=1&FN='

# Output files
MEMBERS_FILE_JSON = 'data/members.json'


logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

session = HTMLSession()

members = []


def scrape_all():
    logger.info("Scraping all Members' data")

    # Get everything except the mgMemberIndex.aspx bit:
    parsed_url = urlparse(MEMBERS_LIST_URL)
    path = '/'.join( parsed_url[2].split('/')[:-1] )
    base_url = '{}://{}{}'.format(parsed_url[0], parsed_url[1], path)

    r = session.get(MEMBERS_LIST_URL)


    rows = r.html.find('.mgStatsTable tbody tr')


    for row in rows:
        (photo_cell, member_cell, party_cell, ward_cell) = row.find('td')

        # Get name and URL

        member_link =  member_cell.find('p', first=True).find('a', first=True)

        url = member_link.attrs['href']
        if not url.startswith('http'):
            url = '{}/{}'.format(base_url, url)

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

    with open(MEMBERS_FILE_JSON, 'w') as f:
        json.dump({'members': members}, f, indent=2, ensure_ascii=False)

    logger.info("Saved data for {} members".format(len(members)))


def scrape_member(url):
    logger.info("Scraping a single Members' data")
    logger.info("URL: {}".format(url))



if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='''Scrapes data about Members' from the City of London website.
            Supply the URL of a single Member's page to only fetch their data.
            Otherwise, data about all Members will be fetched.''' )
    parser.add_argument(
        '-u', '--url',
        help="URL of a single Member's page to fetch",
        required=False)
    args = parser.parse_args()

    if args.url:
        scrape_member(args.url)
    else:
        scrape_all()
