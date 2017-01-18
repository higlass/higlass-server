FROM continuumio/miniconda:4.1.11

# "pip install clodius" complained about missing gcc,
# and "apt-get install gcc" failed and suggested apt-get update.
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get --yes install gcc

RUN conda install --yes cython==0.25.2 numpy=1.11.2
RUN conda install --yes --channel bioconda pysam=0.9.1.4 htslib=1.3.2

RUN git clone --depth=1 --branch=mccalluc/get-build-working https://github.com/hms-dbmi/higlass-server.git
WORKDIR higlass-server/

RUN pip install clodius==0.3.2
RUN pip install -r requirements.txt
RUN python manage.py migrate
