FROM continuumio/miniconda3:4.3.14

RUN apt-get update && apt-get install -y \
        gcc=4:4.9.2-2 \
        nginx-full \
        supervisor \
        unzip=6.0-16+deb8u2 \
        uwsgi-plugin-python3 \
        zlib1g-dev=1:1.2.8.dfsg-2+b1 \
        libcurl4-openssl-dev \
        g++ \
        vim \
        build-essential \
        libssl-dev \
        libpng-dev \
        git \
        fuse \
    && rm -rf /var/lib/apt/lists/*

RUN conda install --yes cython==0.25.2 numpy=1.12.0
RUN conda install --yes --channel bioconda pysam htslib=1.3.2
RUN pip install uwsgi==2.0.14

RUN pip install simple-httpfs>=0.1.3

ENV HTTPFS_HTTP_DIR /data/media/http
ENV HTTPFS_HTTPS_DIR /data/media/https
ENV HTTPFS_FTP_DIR /data/media/ftp

WORKDIR /higlass-server
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY docker-context/nginx.conf /etc/nginx/
COPY docker-context/hgserver_nginx.conf /etc/nginx/sites-enabled/
RUN rm /etc/nginx/sites-*/default && grep 'listen' /etc/nginx/sites-*/*

COPY docker-context/uwsgi_params ./
COPY docker-context/default-viewconf-fixture.xml ./

COPY docker-context/supervisord.conf ./
COPY docker-context/uwsgi.ini ./

COPY docker-context/httpfs.sh ./

EXPOSE 80

ENV HIGLASS_SERVER_BASE_DIR /data
VOLUME /data
VOLUME /tmp

ARG WORKERS=2
ENV WORKERS ${WORKERS}
RUN echo "WORKERS: $WORKERS"

COPY . .

CMD ["supervisord", "-n", "-c", "/higlass-server/supervisord.conf"]
