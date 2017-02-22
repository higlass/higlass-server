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
if [ -n "$1" ]; then
  SUBSET=.tests.$1
else
  SUBSET=''
fi
SETTINGS=higlass_server.settings_test
python manage.py test tilesets$SUBSET --settings=$SETTINGS

### 2) Django server

# If no test filter was given:
if [ -z "$SUBSET" ]; then

    ### Setup

    # TODO: We need a test DB rather than wiping the default one.
    python manage.py flush --noinput --settings=$SETTINGS
    python manage.py migrate --settings=$SETTINGS

    USER=admin
    PASS=nimda
    echo "from django.contrib.auth.models import User; User.objects.filter(username='$USER').delete(); User.objects.create_superuser('$USER', 'user@host.com', '$PASS')" | python manage.py shell

    PORT=6000
    python manage.py runserver localhost:$PORT --settings=higlass_server.settings_test &
    #DJANGO_PID=$!
    TILESETS_URL="http://localhost:$PORT/api/v1/tilesets/"
    until $(curl --output /dev/null --silent --fail --globoff $TILESETS_URL); do echo '.'; sleep 1; done

    ### Tilesets

    upload_tilesets() {
      curl -u $USER:$PASS \
           -F "uid=$1" \
           -F "filetype=$2" \
           -F "datatype=$3" \
           -F "datafile=@data/$4" \
           -F "coordSystem=hg19" \
           $TILESETS_URL
    }
    upload_tilesets aa cooler matrix $COOLER
    upload_tilesets bb hitile vector $HITILE
    # TODO: Check that the output is what we expect?

    TILESETS_JSON=`curl $TILESETS_URL`
    echo $TILESETS_JSON

    TILESETS_EXPECTED='{"count": 2, "results": [{"uuid": "aa", "filetype": "cooler", "datatype": "matrix", "private": false, "name": "dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool", "coordSystem": "hg19", "coordSystem2": ""}, {"uuid": "bb", "filetype": "hitile", "datatype": "vector", "private": false, "name": "wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile", "coordSystem": "hg19", "coordSystem2": ""}]}'

    [ "$TILESETS_JSON" == "$TILESETS_EXPECTED" ] || exit 1

    ### Viewconf

    #$VIEWCONF_URL="http://localhost:$PORT/api/v1/viewconf/"
    #echo '{}' > data/viewconf.json
    #
    #upload_viewconf() {
    #  curl -F "uid=$1" \
    #       -F "viewconf=@data/$4" \
    #       $VIEWCONF_URL
    #}
    #upload_viewconf viewconf_id viewconf.json
    #
    #VIEWCONF_JSON=`curl $VIEWCONF_URL?d=viewconf_id`
    #echo $VIEWCONF_JSON
    #
    #VIEWCONF_EXPECTED=\
    #'{}'
    #
    #[ "$VIEWCONF_JSON" == "$VIEWCONF_EXPECTED" ] || exit 1

fi

echo 'PASS!'

