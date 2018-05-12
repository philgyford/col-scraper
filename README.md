# City of London councillors data scraper

This repository provides several things:

1. A script that scrapes data from pages at [City of London's Councillors][colc] and saves them into JSON files, which are included here in the `data/` directory. (`scrape_members.py`)

2. A script that converts these JSON files into an SQLite database. (`convert_json_to_sqlite.py`)

3. Configuration to use [Datasette][datasette] to create a web-browsable version of the SQLite database.

4. A Dockerfile suitable for deploying the Datasette interface to something like [Zeit.co][zeit].

Each step is detailed below, along with more information about the structure of the JSON files.

**You can browse the resulting database at https://city-of-london-councillors.now.sh**

I wrote about this project [on my website][post].

The scraping script currently gets basic data about each member (e.g. name, ward, party), their data from the Register of Interests, and their committee memberships. It could fetch more, such as contact details, voting record, etc.

While every effort has been taken to ensure accuracy, I haven't checked every single piece of saved data, so use at your own risk.


## Setup

Install python requirements with:

    pip install -r requirements.txt


## The four steps

From scraping the data through to deploying on Zeit.co.


### 1. Fetching the JSON data

The JSON data is included here, so this step isn't required, but to re-fetch it, or start from scratch:

    python scrape_members.py

Add the `--verbose` flag to see more debug output:

    python scrape_members.py --verbose

You can also fetch an individual member's data if you know their numeric ID (useful for debugging):

    python scrape_members.py --id=292

That won't update any of the "list" JSON files, only the member's individual file.

See below for more information about what the JSON files contain.


### 2. Creating an SQLite database

Assuming all the JSON files are present, you can create an SQLite database by running this command, passing in the name of the database file to create:

    python convert_json_to_sqlite.py colmem.db

You should be able to run it multiple times without things breaking.

The database should be called `colmem.db` for use with the Datasette metadata file in step 3.


### 3. Browse the database with Datasette

Assuming you have an SQLite database from step 2, then run this command:

    datasette colmem.db --metadata datasette_metadata.json

You should now be able to visit http://127.0.0.1:8001 in your browser.


### 4. Deploying to Zeit.co

You could run the Datasette interface anywhere, but here's how to get it running on Zeit.co.

Set up an account on [Zeit.co][zeit].

Install the Zeit command line tools.

Then run:

    now

This will use the `Dockerfile` to create a new deployment of the site. If it works, you will have a new site called something like `col-scraper-abcdefghij.now.sh` which you could visit at `https://col-scraper-abcdefghij.now.sh`

To give this a nicer domain name, give it an alias:

    now alias https://col-scraper-abcdefghij.now.sh my-nice-alias

Which would make the site accessible at `https://my-nice-alias.now.sh`

If you want to update the site, you run `now` again, which creates a brand new deployment. You then need to point your existing alias to this new deployment, by running `now alias` again with the new deployment's URL.

List all the deployments for this app with:

    now ls col-scraper

Remove unused ones with:

    now rm col-scraper-abcdefghij.now.sh


## The JSON files

There are three files listing members, wards and committees, and then a single file for each member.

### Members list file

The file `data/members.json` is of this format:

    {
      "meta": {
        "time_created": "2018-05-02T17:30:32.046751+00:00"
      },
      "members": [
        {
          "id": 292,
          "name": "Edward Lord, OBE, JP",
        },
        etc...
      ]
    }

The `time_created` is the time this file was created.

The numeric IDs are the IDs used in URLs for each member ([such as this][member]), and for the names of the member's individual JSON file within `data/members/` (see below).

### Wards list file

The file `data/wards.json` is of this format:

    {
      "meta": {
        "time_created": "2018-05-02T17:30:32.046751+00:00"
      },
      "wards": [
        {
          "name": "Aldersgate"
        },
        etc...
      ]
    }

The `time_created` is the time this file was created.

There is no more information about each ward, other than the name. This file lists all the wards we have members representing.

### Committees list file

The file `data/committees.json` is of this format:

    {
      "meta": {
        "time_created": "2018-05-02T17:30:32.046751+00:00"
      },
      "committees": [
        {
          "id": 122,
          "name": "Epping Forest & Commons Committee",
          "url": "http://democracy.cityoflondon.gov.uk/mgCommitteeDetails.aspx?ID=122"
        },
        etc...
      ]
    }

The `time_created` is the time this file was created.

The numeric IDs are the IDs used in URLs for each committee ([such as this][committee]), and are used when listing a member's committee memberships in the individual member files (see below).

### Members detail files

There is a file within `data/members/` for each member, named using their ID. e.g. `data/members/292.json`. This contains all the data we have about that member, including info from their page ([like this one][member]) and from their Register of Interests page ([like this][interests]).

The data is of this format (this is a truncated version of one of the files):

    {
      "meta": {
        "time_created": "2018-05-02T17:27:38.786055+00:00"
      },
      "member": {
        "id": 292,
        "url": "http://democracy.cityoflondon.gov.uk/mgUserInfo.aspx?UID=292",
        "name": "Edward Lord, OBE, JP",
        "role": "Deputy",
        "ward": "Farringdon Without",
        "party": ""
      },
      "committees": [
        {
          "id": 1255,
          "name": "Capital Buildings Committee",
          "role": "Deputy Chairman"
        }
      ],
      "interests": [
        {
          "name": "Employment, office, trade, profession or vocation",
          "items": [
            {
              "member": "Managing Director: Stakeholder engagement, governancr, philantropy and diversity at Edward Lord Limited",
              "partner": "Senior Lecturer, The Open University"
            }
          ]
        }
      ],
      "gifts": [
        {
          "name": "Champagne reception and Dinner - Honourable Societies of the Inner Temple and Middle Temple",
          "date_str": "14 May 2015",
          "date": "2015-05-14"
        }
      ]
    }

The `time_created` is the time this data was fetched and the file created.

There are four arrays: `member`, `committees`, `interests` and `gifts`.

#### Member

Basic information about the member.

`role` is probably one of "Alderman", "Common Councillor", "Deputy" or "" (empty string).

`ward` is the name of an electoral ward. These are also listed in the `wards.json` file (see above).

`party` is usually (currently) an empty string apart from a couple of "Independent"s.

#### Committees

An array of objects listing all the committee memberships this member has. Each one has:

`id` as used on the website, used in the URL for the committee ([like this one][committee]).

`name` is the name of the commmittee.

`role` is the member's role of the committee, currently one of "Chairman", "Deputy Chairman" "Ex-Officio Member" or "" (empty string).

#### Interests

An array of objects, each one a category of interests. The category has a `name`, such as "Employment, office, trade, profession or vocation".

Each category contains an array of zero or more `item`s, each equivalent to a row in a table on [the web page][interests].

A single `item` object has `member` and `partner` elements, each equivalent to one cell on that web page. We use `partner` as an abbreviation for the full column heading used: "Spouse/Civil Partner/Living as such".

If the value for either of these on the web page was "Nil", "n/a", "None", "-", etc, we use a "" (empty string).

#### Gifts

The gifts come from the "Gifts of Hospitality" table. Each object in the `gifts` array has a `name`, and two dates. `date_str` is the original text from web page. `date` is an attempt to create a `YYYY-MM-DD` date from this string using [dateparser][dateparser]. It's usually accurate but fails on some strings such as "2-3 February 2017", and if no year was supplied. In either case `date` will be `null`.


[colc]: http://democracy.cityoflondon.gov.uk/mgMemberIndex.aspx?VW=TABLE&PIC=1&FN=

[datasette]: https://github.com/simonw/datasette

[zeit]: https://zeit.co/dashboard

[member]: http://democracy.cityoflondon.gov.uk/mgUserInfo.aspx?UID=292

[committee]: http://democracy.cityoflondon.gov.uk/mgCommitteeDetails.aspx?ID=122

[interests]: http://democracy.cityoflondon.gov.uk/mgDeclarationSubmission.aspx?UID=292&HID=3012&FID=0&HPID=505566937

[dateparser]: https://github.com/scrapinghub/dateparser

[post]: http://www.gyford.com/phil/writing/2018/05/10/city-london-councillors-data/
