#!/usr/bin/env bash

git pull

pip install -r ./requirements.txt

pip install -r ./requirements-secondary.txt

python manage.py migrate
