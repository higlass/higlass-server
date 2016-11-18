# higlass-server

## Installation

1. clone repo
2. `cd higlass-server/`
3. `pip install --upgrade -r requirements.txt`
4. resolve personal dependency issues that pip can't
5. ensure access to port 8000
6. `mkdir higlass-server/data`
7. `python run_tornado.py` or `python manage.py runserver localhost:8000`

## Jump start

These steps are optional in case one wants to start with a pre-populated database.

Run the server:

```
python manage.py makemigrations
python manage.py migrate
python manage.py runserver localhost:8000
```

Add a dataset

```
wget https://s3.amazonaws.com/pkerp/public/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
mv dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool data/
curl -H "Content-Type: application/json" -X POST -d '{"processed_file":"data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool","file_type":"cooler"}' http://localhost:8001/tilesets/
```

This will return a UUID. This uuid can be used to retrieve tiles:

Get tileset info:

```
curl http://localhost:8001/tilesets/db/tileset_info/?d=767fc12a-f351-4678-8d23-d08996b4d7e4
```

Get a tile:

```
curl http://localhost:8001/tilesets/db/render/?d=acd52643-57ba-4a4d-9796-7e0b3ac8380e.0.0.0
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
