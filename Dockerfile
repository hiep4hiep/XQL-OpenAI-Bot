FROM python:3.9.16
RUN mkdir /var/lib/xqlbot
WORKDIR /var/lib/xqlbot
ADD requirements.txt .
RUN pip install -r requirements.txt