import argparse
from requests_html import HTML


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
        print(args.url)

    else:
        print("no")
