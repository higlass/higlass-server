#!/usr/bin/env bash

git pull

pip install -r ./requirements.txt

python manage.py migrate
