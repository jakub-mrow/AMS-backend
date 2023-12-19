FROM python:3.11-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY ./docker/django/requirements.txt .

# copy django scripts
COPY ./docker/django/scripts/* /usr/local/bin/

RUN chmod +x /usr/local/bin/*

# install requirements
RUN pip install --upgrade pip \
    pip install -r requirements.txt

WORKDIR /code

COPY . .

WORKDIR /code/src

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
