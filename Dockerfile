FROM python:2.7

RUN git clone --depth=1 --branch=mccalluc/get-build-working https://github.com/hms-dbmi/higlass-server.git
WORKDIR higlass-server/
#RUN pip install --upgrade -r requirements.txt
#RUN python manage.py migrate
