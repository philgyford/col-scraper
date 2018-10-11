FROM python:3.6-slim-stretch
RUN apt update
RUN apt install -y python3-dev gcc wget
COPY . /app
WORKDIR /app
RUN pip install pipenv
RUN pipenv install --skip-lock --system
RUN python convert_json_to_sqlite.py colmem.db
RUN datasette inspect colmem.db --inspect-file inspect-data.json

EXPOSE 8001

CMD datasette serve colmem.db --host 0.0.0.0 --cors --port 8001 --inspect-file inspect-data.json -m datasette_metadata.json
