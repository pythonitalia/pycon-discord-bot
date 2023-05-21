FROM python:3.11

RUN pip install pdm

COPY . /app

WORKDIR /app

RUN pdm install

CMD ["pdm", "start"]
