FROM python:3.11-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

# install requirements
RUN pip install --upgrade pip \
    pip install -r requirements.txt

WORKDIR /code

COPY . .

WORKDIR /code/src

CMD ["celery", "-A", "main", "beat", "-l", "INFO"]
