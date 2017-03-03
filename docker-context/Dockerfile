# This Dockerfile makes it easy to get a basic development environment,
# but it should not be used for production: It is bloated, and
# dependencies are not pinned.

# Typical usage:
#
# git clone https://github.com/hms-dbmi/higlass-server.git
# docker build --cache-from higlass-server-image --tag higlass-server-image docker-context
# docker run -dit --name higlass-server-container --volume `pwd`:/home/higlass/higlass-server higlass-server-image
# docker exec higlass-server-container python manage.py migrate
# docker exec -it higlass-server-container /bin/bash

FROM ubuntu

RUN apt-get update
RUN apt-get -y install libatlas-dev libatlas-base-dev liblapack-dev gfortran wget bzip2 git libz-dev curl
RUN useradd --create-home --shell /bin/bash higlass

USER higlass
WORKDIR /home/higlass

RUN wget http://repo.continuum.io/miniconda/Miniconda2-4.2.12-Linux-x86_64.sh -O miniconda.sh
RUN bash miniconda.sh -b -p /home/higlass/miniconda
ENV PATH="/home/higlass/miniconda/bin:${PATH}"
RUN conda install --yes python=2.7.12 cython==0.25.2 numpy=1.11.2

# This is not run with bash: Otherwise, the <( ) syntax would be useful here.
ENV GITHUB=https://raw.githubusercontent.com/hms-dbmi/higlass-server/master
RUN wget $GITHUB/requirements.txt           && pip install -r requirements.txt
RUN wget $GITHUB/requirements-secondary.txt && pip install -r requirements-secondary.txt

WORKDIR higlass-server
