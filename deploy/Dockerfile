FROM python:3.6-slim-stretch
RUN apt update
RUN apt install -y python3-dev gcc wget
ADD metadata.json metadata.json
RUN pip install -r requirements.txt
RUN pip install https://github.com/simonw/datasette/archive/master.zip
CMD python3 ../convert_json_to_sqlite.py colmem.db
RUN datasette inspect colmem.db --inspect-file inspect-data.json

EXPOSE 8001

CMD datasette serve colmem.db --host 0.0.0.0 --cors --port 8001 --inspect-file inspect-data.json -m metadata.json
