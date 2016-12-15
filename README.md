# higlass-server

## Installation

```bash
git clone https://github.com/hms-dbmi/higlass-server.git
cd higlass-server/
pip install --upgrade -r requirements.txt
python manage.py migrate
python manage.py runserver localhost:8000
```

## Jump start

These steps are optional in case one wants to start with a pre-populated database.

```
wget https://s3.amazonaws.com/pkerp/public/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
mv dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool data/

wget https://s3.amazonaws.com/pkerp/public/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
mv wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile data/

curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool","file_type":"cooler", "uid": "aa"}' http://localhost:8000/tilesets/
curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile","file_type":"hitile", "uid": "bb"}' http://localhost:8000/tilesets/
```

This will return a UUID. This uuid can be used to retrieve tiles:

Get tileset info:

```
curl http://localhost:8000/tileset_info/?d=aa
```

Get a tile:

```
curl http://localhost:8000/tiles/?d=aa.0.0.0
```

### Preparing cooler files for use with `higlass-server`

[Cooler](https://github.com/mirnylab/cooler) files store Hi-C data. They need to be decorated with aggregated data at multiple resolutions in order to work with `higlass-server`.
This is easily accomplished by simply installing the `cooler` python package and running the `recursive_agg_onefile.py` script. For now this has to come from a clone of the
official cooler repository, but this will hopefully be merged into the main branch shortly.

```

git clone -b develop https://github.com/pkerpedjiev/cooler.git
cd cooler
python setup.py install

recursive_agg_onefile.py file.cooler --out output.cooler
```

### Preapring bigWig files for use with `higlass-server`

[BigWig](https://genome.ucsc.edu/goldenpath/help/bigWig.html) files contain values for positions along a genome. To be viewable using higlass, they need to be aggregated using `clodius`:

Installing `clodius`:

```
pip install clodius
```

Getting a sample dataset:

```
wget http://hgdownload.cse.ucsc.edu/goldenpath/hg19/encodeDCC/wgEncodeCaltechRnaSeq/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.bigWig
```

Aggregate it:

```
tile_bigWig.py wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.bigWig --output-file data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
```

Register it:

```
curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2","file_type":"hitile"}' http://localhost:8000/tilesets/
```

### Registering a cooler file

See the "Add a dataset" line in the "Jump Start" section above.

### Unit tests

```
wget https://s3.amazonaws.com/pkerp/public/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
mv dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool data/

wget https://s3.amazonaws.com/pkerp/public/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
mv wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile data/

python manage.py test tilesets
```

### Upgrade

```
bumpversion patch
```
