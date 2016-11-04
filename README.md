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

[8]. = `wget https://s3.amazonaws.com/pkerp/public/db.sqlite3`
[9]. = `wget https://s3.amazonaws.com/pkerp/public/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool`
[10]. `mv https://s3.amazonaws.com/pkerp/public/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool data`

Run the server:

`python manage.py runserver localhost:8000`

Get a tile:

`curl http://54.70.83.188:8000/coolers/12/tiles/?data=/0.0.0`

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

