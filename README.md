# higlass-server

## Easy Docker install

A higlass-server image is available on [DockerHub](https://hub.docker.com/r/gehlenborglab/higlass-server/).
Install Docker on your system, and then:

```bash
# download:
docker pull gehlenborglab/higlass-server

# start container:
#   Port 8000 is hardcoded in the image;
#   Port 8001 is what it should be mapped to on the host.
docker run --name my-higlass-server --detach --publish 8001:8000 gehlenborglab/higlass-server
curl http://localhost:8001/

# connect to an already running container:
docker exec --interactive --tty my-higlass-server bash

# remove all containers (use with caution):
docker ps -a -q | xargs docker stop | xargs docker rm
```

## Installation from source

**Note:** We recommend creating a virtual environment for higlass-server after cloning, e.g.: 
`virtualenv ~/higlass-server-env && source ~/higlass-server-env/bin/activate`, to avoid conflicts.

```bash
git clone https://github.com/hms-dbmi/higlass-server.git && cd higlass-server
pip install --upgrade -r requirements.txt
pip install --upgrade -r requirements-secondary.txt
python manage.py migrate
python manage.py runserver localhost:8000
```

## Jump start

These steps are optional in case one wants to start with a pre-populated database.

```
COOLER=dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
HITILE=wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile

wget -P data/ https://s3.amazonaws.com/pkerp/public/$COOLER
wget -P data/ https://s3.amazonaws.com/pkerp/public/$HITILE

python manage.py ingest_tileset --filename data/$COOLER --filetype cooler --datatype matrix --uid aa
python manage.py ingest_tileset --filename data/$HITILE --filetype hitile --datatype vector --uid bb
```

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

### Preparing bigWig files for use with `higlass-server`

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
wget -O -P data/ https://s3.amazonaws.com/pkerp/public/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
wget -O -P data/ https://s3.amazonaws.com/pkerp/public/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile
wget -O -P data/ https://s3.amazonaws.com/pkerp/public/gene_annotations.short.db

python manage.py test tilesets
```

### Upgrade

```
bumpversion patch
```
