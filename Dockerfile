FROM continuumio/miniconda3:4.3.14

RUN apt-get update && apt-get install -y \
        gcc=4:4.9.2-2 \
        unzip=6.0-16+deb8u2 \
        uwsgi-plugin-python3 \
        zlib1g-dev=1:1.2.8.dfsg-2+b1 \
        libcurl4-openssl-dev \
        g++ \
        vim \
        build-essential \
        libssl-dev \
        libpng-dev \
    && rm -rf /var/lib/apt/lists/*

RUN conda install --yes cython==0.25.2 numpy=1.12.0
RUN conda install --yes --channel bioconda pysam htslib=1.3.2

WORKDIR /higlass-server
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY requirements-secondary.txt ./
RUN pip install -r requirements-secondary.txt

RUN mkdir -p /data/log

EXPOSE 8000

COPY . .
RUN python manage.py migrate

ENTRYPOINT ["python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
