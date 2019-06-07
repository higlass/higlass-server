#!/bin/bash

umount media/http
umount media/https

simple-httpfs.py media/http
simple-httpfs.py media/https

python manage.py runserver
