#!/usr/bin/env bash
set -e

### Build and test from the inside out:
### 1) Unit tests

COOLER=dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
HITILE=wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile

FILES=$(cat <<END
$COOLER
$HITILE
Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool
gene_annotations.short.db
cnv_short.hibed
arrowhead_domains_short.txt.multires.db
hiccups_loops_short.txt.multires.db
END
)

for FILE in $FILES; do
  [ -e data/$FILE ] || wget -P data/ https://s3.amazonaws.com/pkerp/public/$FILE
done
echo 'foo bar' > data/tiny.txt
python manage.py test tilesets

### 2) Django server

USER=admin
PASS=nimda
echo "from django.contrib.auth.models import User; User.objects.filter(username='$USER').delete(); User.objects.create_superuser('$USER', 'user@host.com', '$PASS')" | python manage.py shell

PORT=6000
python manage.py runserver localhost:$PORT &
DJANGO_PID=$!
URL="http://localhost:$PORT/api/v1/tilesets/"
until $(curl --output /dev/null --silent --fail --globoff $URL); do echo '.'; sleep 1; done

upload() {
  curl -u $USER:$PASS \
       -F "uid=$1" \
       -F "filetype=$2" \
       -F "datatype=$3" \
       -F "datafile=@data/$4" \
       -F "coordSystem=hg19" \
       $URL
}
upload aa cooler matrix $COOLER
upload bb hitile vector $HITILE
# TODO: Check that the output is what we expect?

JSON=`curl $URL`
echo $JSON

EXPECTED=\
'{"count": 2, "results": ['\
'{"uuid": "aa", "filetype": "cooler", "datatype": "matrix", "private": false, '\
'"name": "'$COOLER'", "coordSystem": "hg19", "coordSystem2": ""}, '\
'{"uuid": "bb", "filetype": "hitile", "datatype": "vector", "private": false, '\
'"name": "'$HITILE'", "coordSystem": "hg19", "coordSystem2": ""}]}'

[ "$JSON" == "$EXPECTED" ] || exit 1

kill $DJANGO_PID

echo 'PASS!'
