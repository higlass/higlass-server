#!/usr/bin/env bash
set -e

### Build and test from the inside out:
### 1) Unit tests

COOL=dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
MM9COOL=Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool
HITILE=wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
ANNO=gene_annotations.short.db
HIBED=cnv_short.hibed
AHBED=arrowhead_domains_short.txt.multires.db
HLBED=hiccups_loops_short.txt.multires.db

for FILE in $COOL $MM9COOL $HITILE $ANNO $HIBED $AHBED $HLBED; do
  [ -e data/$FILE ] || wget https://s3.amazonaws.com/pkerp/public/$FILE  && mv $FILE data/
done
echo 'foo bar' > data/tiny.txt
python manage.py test tilesets

### 2) Django server

PORT=6000
echo "from django.contrib.auth.models import User; User.objects.filter(username='admin').delete(); User.objects.create_superuser('admin', 'user@host.com', 'nimda')" | python manage.py shell
python manage.py runserver localhost:$PORT &
URL="http://localhost:$PORT/api/v1/tilesets/"
until $(curl --output /dev/null --silent --fail --globoff $URL); do echo '.'; sleep 1; done

curl -u admin:nimda -F "datafile=@data/$COOL" -F "filetype=cooler" -F "datatype=matrix" -F "uid=aa" -F "coordSystem=hg19" $URL
curl -u admin:nimda -F "datafile=@data/$HITILE" -F "filetype=hitile" -F "datatype=vector" -F "uid=bb" -F "coordSystem=hg19" $URL
# TODO: Check that the output is what we expect?

JSON=`curl $URL`
echo $JSON
EXPECTED=\
'{"count": 2, "results": ['\
'{"uuid": "aa", "filetype": "cooler", "datatype": "matrix", "private": false, '\
'"name": "dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool", "coordSystem": "hg19", "coordSystem2": ""}, '\
'{"uuid": "bb", "filetype": "hitile", "datatype": "vector", "private": false, '\
'"name": "wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile", "coordSystem": "hg19", "coordSystem2": ""}]}'
[ "$JSON" == "$EXPECTED" ] && echo "Got expected response. Yay!"