FROM python:3.9.0-alpine3.12

WORKDIR /opt/prometheus-s3-exporter
COPY app/requirements.txt ./
RUN apk add build-base
RUN pip install --no-cache-dir -r requirements.txt
RUN apk del build-base

RUN adduser -D -H exporter

COPY --chown=nobody app ./
RUN chmod u-w -R ./; python -m compileall .

USER exporter
EXPOSE 9327
VOLUME "/config"
CMD ["python", "./exporter.py"]
