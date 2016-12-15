# higlass-server

## Installation

1. clone repo
2. `cd higlass-server/`
3. `pip install --upgrade -r requirements.txt`
4. resolve personal dependency issues that pip can't
5. ensure access to port 8000
6. `python run_tornado.py` or `python manage.py runserver localhost:8000`

## Jump start

These steps are optional in case one wants to start with a pre-populated database.

Run the server:

```
python manage.py makemigrations
python manage.py migrate
python manage.py runserver localhost:8000
```

Add two datasets

```
curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool","file_type":"cooler", "uid": "aa"}' http://localhost/tilesets/
curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile","file_type":"hitile", "uid": "bb"}' http://localhost/tilesets/
```

In this case, we are providing UUIDs for each tileset. In practice, this is
discouraged as it may lead to clashes with existing UUIDs. It's better not to
provide this field and to get it from the response.

Get tileset info:

```
curl http://localhost:8001/tileset_info/?d=aa
curl http://localhost:8001/tileset_info/?d=bb
```

Get a tile:

```
curl http://localhost:8001/tiles/?d=aa.0.0.0
curl http://localhost:8001/tiles/?d=bb.0.0
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
wget http://egg2.wustl.edu/roadmap/data/byFileType/signal/consolidated/macs2signal/foldChange/E002-H3K4me3.fc.signal.bigwig
```

Aggregate it:

```
python scripts/tile_bigWig.py --assembly hg19 --output-file E002-H3K4me3.fc.signal.hitile E002-H3K4me3.fc.signal.bigwig
```

Register it:

```
curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/E002-H3K4me3.fc.signal.hitile","file_type":"hitile"}' http://localhost:8000/tilesets/
```

### Registering a cooler file

See the "Add a dataset" line in the "Jump Start" section above.

### Benchmarking

The file `doc/tile_requests` has a list of tiles requested for a 2D map. A potential benchmark for the performance of the server is seeing how long it takes to retrieve that set of tiles.

Example sequential run:

```
/usr/bin/time python scripts/benchmark_server.py http://localhost:8001 674df80b-c157-4b5a-b6d4-64f99f990374 --tile-id-file doc/less_tile_requests.txt
```

Example multi-tile request

```
/usr/bin/time python scripts/benchmark_server.py http://localhost:8001 674df80b-c157-4b5a-b6d4-64f99f990374 --tile-id-file doc/less_tile_requests.txt --at-once
```

### Unit tests

```
python manage.py test tilesets
```

#### Resetting the database

```
rm -f tmp.db db.sqlite3; rm -r tilesets/migrations; python manage.py makemigrations tilesets; python manage.py migrate
```
