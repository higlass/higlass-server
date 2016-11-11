# higlass-server

## Installation

1. clone repo
2. `cd higlass-server/api`
3. `pip install --upgrade -r requirements.txt`
4. resolve personal dependency issues that pip can't
5. ensure access to port 8000
6. `mkdir /higlass-server/api/data`
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
cd api
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

## Usage

To access the API interactively, please visit http://54.70.83.188:8000/


### Uploading Data
To upload a new cooler file, format a POST request according to the interactive specification at http://54.70.83.188:8000/coolers/


### Processing Data

To generate multires cooler files in the db for a dataset for which metadata has been uploaded to the database via a POST request visit http://54.70.83.188:8000/coolers/x/generate_tiles replacing x with cooler object id from coolers table


To view info about a specific cooler visit http://54.70.83.188:8000/coolers/x replacing x with cooler object id from coolers table


To view tileset info in a specific multires cooler view http://54.70.83.188:8000/coolers/x/tileset_info replacing x with cooler object id from coolers table


To retrieve a tile visit http://54.70.83.188:8000/coolers/t/tiles/?data=/x.y.z replacing t with cooler object id from coolers table, x&y with coordinates, and z with zoom level. 


To view users table (if admin auth provided) visit http://54.70.83.188:8000/users/


To view more detailed schema visit http://54.70.83.188:8000/schema


To administer visit http://54.70.83.188:8000/admin 
 

Test Accounts:
u Root: p higlassdbmi
u test: p higlassdbmi

Root account will show all data in the coolers table while test will only show public tables + tables owned by the user test. The API can be accessed without logging in for datasets that have been uploaded as "public" (boolean included in the POST request).  

### Benchmarking

The file `doc/tile_requests` has a list of tiles requested for a 2D map. A potential benchmark for the performance of the server is seeing how long it takes to retrieve that set of tiles.

Example sequential run:

```
/usr/bin/time python scripts/benchmark_server.py http://localhost:8001 767fc12a-f351-4678-8d23-d08996b4d7e4 --tile-id-file doc/less_tile_requests.txt
```

Example multi-tile request

```
/usr/bin/time python scripts/benchmark_server.py http://localhost:8001 767fc12a-f351-4678-8d23-d08996b4d7e4 --tile-id-file doc/less_tile_requests.txt --at-once
```
