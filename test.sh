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

SETTINGS=higlass_server.settings_test

python manage.py migrate --settings=$SETTINGS

PORT=6000
python manage.py runserver localhost:$PORT --settings=$SETTINGS &
#DJANGO_PID=$!
TILESETS_URL="http://localhost:$PORT/api/v1/tilesets/"
until $(curl --output /dev/null --silent --fail --globoff $TILESETS_URL); do echo '.'; sleep 1; done
# Server is needed for higlass_server tests

python manage.py test -v 2 tilesets higlass_server --settings=$SETTINGS

echo 'PASS!'

