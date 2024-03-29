# AMS backend - getting started

## Prerequisites
- docker and docker-compose

### Build project
```
docker-compose build
```

### Run containers
```
docker-compose up
```
### Stop containers
```
docker-compose down
```

### Database migration
On every setup, database migration is required

```
docker-compose exec django manage migrate
```

If manage script does not work then

```
docker-compose exec django python manage.py migrate
```

### Creating new migration files
```
docker-compose exec django manage makemigrations
```

### Create dev user and generate tokens
```
docker-compose exec django manage generate_dev_tokens -u <user> -p <password> -e <email>
```

### Running tests

Enter django container shell
```
docker-compose exec django bash
```

Run all the tests
```
pytest .
```
Run specific test
```
pytest -vv -x -k <test_name>
```

### Connecting to database

Enter into container through command below or using docker desktop
```
docker-compose exec postgres bash
```

```
psql -U postgres -d postgres
```

To list all the tables
```
\dt
```


### Pipenv configuration
Installing pipenv to python3
```
pip install pipenv
```


How to add package to pipenv
1. Adding line to Pipfile
    ```
    pytest-django= "==4.5.2"
    ```
2. Executing command in terminal
    ```
   pipenv install "pytest-django==4.5.2"
   ```

### Exchanges
Load exchanges into database
```
docker-compose exec django python manage.py insert_exchanges_to_db
```
