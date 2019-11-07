#!/bin/bash

umount media/http
umount media/https

simple-httpfs.py media/http
simple-httpfs.py media/https

python manage.py test fragments.tests.FragmentsTest --failfast
python manage.py test tilesets.tests.BamTests --failfast
python manage.py test tilesets.tests.FileUploadTest --failfast
python manage.py test tilesets.tests.MultivecTests --failfast

#python manage.py test tilesets --failfast
