#!/usr/bin/env bash
set -e

# kill previous instances
# ps aux | grep runserver | grep 6000 | awk '{print $2}' | xargs kill
# rm db_test.sqlite3

### Build and test from the inside out:
### 1) Unit tests

# clear previous db
rm db_test.sqlite3 ||:

COOLER=dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
HITILE=wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile

FILES=$(cat <<END
$COOLER
dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.mcoolv2
$HITILE
Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool
gene_annotations.short.db
cnv_short.hibed
arrowhead_domains_short.txt.multires.db
hiccups_loops_short.txt.multires.db
G15509.K-562.2_sampleDown.multires.cool
chromSizes.tsv
gene-annotations-mm9.db
Rao_RepH_GM12878_InsulationScore.txt.multires.db
hic-resolutions.cool
wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.bigWig
wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
chr21.KL.bed.multires.mv5
sample.bed.multires.mv5
984627_PM16-00568-A_SM-9J5GB.beddb
chromInfo_mm9.txt
chromSizes_hg19_reordered.tsv
SRR1770413.sorted.short.bam
SRR1770413.sorted.short.bam.bai
SRR1770413.different_index_filename.bai
SRR1770413.mismatched_bai.bam
END
)

for FILE in $FILES; do
  [ -e data/$FILE ] || wget -P data/ https://s3.amazonaws.com/pkerp/public/$FILE
done

#
# bigBed
#
wget -P data/ https://s3.amazonaws.com/areynolds/public/chromSizes_hg38_bbtest.tsv
wget -P data/ https://s3.amazonaws.com/areynolds/public/masterlist_DHSs_733samples_WM20180608_all_mean_signal_colorsMax.bed.bb

echo 'foo bar' > data/tiny.txt

SETTINGS=higlass_server.settings_test

python manage.py migrate --settings=$SETTINGS

export SITE_URL="somesite.com"
PORT=6000
python manage.py runserver localhost:$PORT --settings=$SETTINGS &

#DJANGO_PID=$!
TILESETS_URL="http://localhost:$PORT/api/v1/tilesets/"
until $(curl --output /dev/null --silent --fail --globoff $TILESETS_URL); do echo '.'; sleep 1; done
# Server is needed for higlass_server tests

python manage.py test -v 2 tilesets higlass_server fragments --settings=$SETTINGS

echo 'PASS!'

# kill all child processes of this bash script
# e.g.: the server
kill $(ps -o pid= --ppid $$)
