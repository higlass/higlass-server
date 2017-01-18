FROM continuumio/miniconda:4.1.11

RUN git clone --depth=1 --branch=mccalluc/get-build-working https://github.com/hms-dbmi/higlass-server.git
WORKDIR higlass-server/
RUN conda install --yes cython==0.25.2 numpy=1.11.2

# "pip install clodius" complained about missing gcc,
# and "apt-get install gcc" failed and suggested apt-get update
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get --yes install gcc

RUN pip install clodius==0.3.2
RUN pip install -r requirements.txt
RUN python manage.py migrate
