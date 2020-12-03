FROM python:3.9.0-alpine3.12

WORKDIR /opt/prometheus-s3-exporter
COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser -D -H exporter

COPY --chown=nobody app ./
RUN chmod u-w -R ./; python -m compileall .

USER exporter
EXPOSE 9327
VOLUME "/config"
ENTRYPOINT ["python", "./exporter.py"]
CMD ["/config/config.yml"]
