# HiGlass Server

The HiGlass Server supports [HiGlass](https://github.com/higlass/higlass) and [HiPiler](https://github.com/flekschas/hipiler)
by providing APIs for accessing and uploading tiles generated by
[Clodius](https://github.com/higlass/clodius).

[![demo](https://img.shields.io/badge/higlass-👍-red.svg?colorB=0f5d92)](http://higlass.io)
[![api](https://img.shields.io/badge/api-documentation-red.svg?colorB=0f5d92)](API.md)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1308945.svg)](https://doi.org/10.5281/zenodo.1308945)


_Note: that the HiGlass Server itself only provides an API, and does not serve any HTML._

## Installation

**Prerequirements**:

- Python v3

### Docker

The easiest way to run HiGlass with HiGlass Server is with Docker. More information is available at [higlass-docker](https://github.com/higlass/higlass-docker#readme) or check out the [Dockerfile](docker-context/Dockerfile).

This project also includes a Dockerfile in the docker-context directory that can be used to run a locally checked out copy of higlass-server as follows:
```bash
docker build -t higlass-server -f docker-context/Dockerfile .
docker run -d --cap-add SYS_ADMIN --device /dev/fuse --security-opt apparmor:unconfined --name higlass-server higlass-server
```

### Manually

To install HiGlass Server manually follow the steps below. Note we strongly recommend to create a virtual environment using [Virtualenvwrapper](https://pypi.python.org/pypi/virtualenvwrapper) for example. Skip step 2 if you don't work with virtual environments.

```bash
git clone https://github.com/higlass/higlass-server && cd higlass-server
mkvirtualenv -a $(pwd) -p $(which python3) higlass-server && workon higlass-server
pip install --upgrade -r ./requirements.txt
python manage.py runserver
```

To enable the register_url api endpoint, HiGlass depends on a project called httpfs to cache external url files. Tests depend on this process running. Set it up as follows:
```bash
pip install simple-httpfs

simple-httpfs.py media/http
simple-httpfs.py media/https
```

Or simply use `./unit_tests.sh`.

---

## Uploading Files

Although there is an API endpoint for uploading files, but it is more direct to use a `manage.py` script:
```
COOLER=dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool
HITILE=wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile

wget -P data/ https://s3.amazonaws.com/pkerp/public/$COOLER
wget -P data/ https://s3.amazonaws.com/pkerp/public/$HITILE

python manage.py ingest_tileset --filename data/$COOLER --filetype cooler --datatype matrix --uid cooler-demo
python manage.py ingest_tileset --filename data/$HITILE --filetype hitile --datatype vector --uid hitile-demo
```

We can now use the API to get information about a tileset, or to get the tile data itself:
```
curl http://localhost:8000/api/v1/tileset_info/?d=hitile-demo
curl http://localhost:8000/api/v1/tiles/?d=hitile-demo.0.0.0
```

---

## Development

**Start** the server:

```
python manage.py runserver localhost:8001
// or
npm start
```

**Test** the server:

```
./test.sh
// or
npm test
```

**Bump version** of server:

```
bumpversion patch
```

**Update** source code:

```
./update.sh
```

## Troubleshooting

**pybbi installation fails on macOS**: Check out https://github.com/nvictus/pybbi/issues/2

## License

The code in this repository is provided under the MIT License.
