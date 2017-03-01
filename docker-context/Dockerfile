# This Dockerfile makes it easy to get a basic development environment,
# but it should not be used for production: It is bloated, and
# dependencies are not pinned.

# (If you want to edit files with an outside IDE, you'll want the
# sourcecode to be in a mounted volume, but then "pip install" here
# wouldn't work. This is not the best solution for everyone.)

# Typical usage:
# $ cd docker-context
# $ docker build --cache-from higlass-server-image --tag higlass-server-image .
# $ docker run -dit --name higlass-server-container higlass-server-image
# $ docker exec -it higlass-server-container /bin/bash

FROM ubuntu

RUN apt-get update
RUN apt-get -y install libatlas-dev libatlas-base-dev liblapack-dev gfortran wget bzip2 git libz-dev curl nano
RUN useradd --create-home --shell /bin/bash higlass

USER higlass
WORKDIR /home/higlass

RUN wget http://repo.continuum.io/miniconda/Miniconda2-4.2.12-Linux-x86_64.sh -O miniconda.sh
RUN bash miniconda.sh -b -p /home/higlass/miniconda
ENV PATH="/home/higlass/miniconda/bin:${PATH}"
RUN conda install --yes python=2.7.12 cython==0.25.2 numpy=1.11.2

RUN git clone https://github.com/hms-dbmi/higlass-server.git

WORKDIR higlass-server

RUN pip install -r requirements.txt
RUN pip install -r requirements-secondary.txt
RUN python manage.py migrate
# As part of the tests, we upload a file that would exhaust a container's disk,
# so at least one failure is expected
#RUN ./test.sh
