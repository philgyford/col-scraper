# City of London members data scraper

There are currently two scripts here:

* `scrape_members.py` scrapes the [City of London's Councillors][colc] page and creates the JSON files included here in the `data/` directory.

* `convert_json_to_sqlite.py` uses those JSON files to create an SQLite database of the data.

[colc]: http://democracy.cityoflondon.gov.uk/mgMemberIndex.aspx?VW=TABLE&PIC=1&FN=

Install requirements with:

    pip install -f requirements.txt

This is currently focused on the Register of Interests data, and only fetches a small amount of general data about Members. It could fetch more, such as contact details, committee appointments, etc.


## Fetching the JSON data

The JSON data is included here, but to re-fetch it, or start from scratch:

    python ./scrape_members.py

Add the `--verbose` flag to see more debug output:

    python ./scrape_members.py --verbose

You can also fetch an individual Member's data if you know their numeric ID (useful for debugging):

    python ./scrape_members.py --id=292

## The JSON files

There is a single file containing basic data about every Member. And then a file for each Member containing information from their Register of Interests.

### Members file

The file `data/members.json` is of this format:

    {
      "meta": {
        "time_created": "2018-05-02T17:30:32.046751+00:00"
      },
      "members": [
        {
          "id": 131,
          "name": "George Christopher Abrahams",
          "url": "http://democracy.cityoflondon.gov.uk/mgUserInfo.aspx?UID=131",
          "role": "Common Councillor",
          "party": "",
          "ward": "Farringdon Without"
        },
        etc...
      ]
    }

The `time_created` is the time this data was fetched and the file created.

The numeric IDs are the IDs used in URLs for each Member.

### Interests files

There is a file within `data/members/` for each Member, named using their ID. e.g. `data/members/292.json`. This contains data from their Register of Interests page. [Here's an example.](interests)

The data is of this format:

    {
      "meta": {
        "time_created": "2018-05-02T17:27:38.786055+00:00"
      },
      "member": {
        "id": 151
      },
      "interests": [
        {
          "name": "Employment, office, trade, profession or vocation",
          "items": [
            {
              "member": "Non-executive Director, Accumuli PLC",
              "partner": "Director, Hampden and Co"
            },
          ]
        },
      ],
      "gifts": [
        {
          "name": "Gresham College Stakeholder Presentation & Dinner (Worshipful Company of Mercers)",
          "date_str": "22 February 2018",
          "date": "2018-02-22"
        }
      ]
    }

The `time_created` is the time this data was fetched and the file created.

There are two arrays, `interests` and `gifts`.

#### Interests

Each object within `interests` is a category of declared interests. It has a name, such as "Employment, office, trade, profession or vocation".

Each of these categories has an array of zero or more `item`s, each equivalent to a row in a table on [the web page][interests].

A single `item` object has `member` and `partner` elements, each equivalent to one cell on that web page. We use `partner` as an abbreviation for the full column heading used: "Spouse/Civil Partner/Living as such".

If the value for either of these was "Nil", "n/a", "None", "-", etc, we use an empty string.

#### Gifts

The gifts come from the "Gifts of Hospitality" table. Each object in the `gifts` array has a `name`, and two dates. `date_str` is the original text from web page. `date` is an attempt to create a `YYYY-MM-DD` date from this string using [dateparser](https://github.com/scrapinghub/dateparser). It's usually accurate but fails on some strings such as "2-3 February 2017", and if no year was supplied. In either case `date` will be `null`.

[interests]: http://democracy.cityoflondon.gov.uk/mgDeclarationSubmission.aspx?UID=292&HID=2996&FID=0&HPID=505557255

## Creating the SQLite database

Assuming all the JSON files are present, you can create an SQLite database by running this command, passing in the name of the database file to create:

    python convert_json_to_sqlite.py register.db

You should be able to run it multiple times without things breaking...
