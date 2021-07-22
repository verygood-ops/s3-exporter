# s3-exporter

Prometheus metrics exporter for S3 Storage

## Config example

```yml
access_key: "optional-your-access-key"
secret_key: "optional-your-secret-key"
bucket: "bucket-name"
patterns:
  - "*.zip"
folders:
  - "backup"
  - "nextcloudbackup"

```

You can omit `access_key` and `secret_key` to use credentials from
environment settings, see the [Boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html) for more info.

If you would like metrics on objects in the root of the bucket use an empty
folder, i.e.:

```
folders:
  - ""
```

## Metrics

Metrics will be available at http://localhost:9327

```sh
# HELP s3_latest_file_timestamp Last modified timestamp(milliseconds) for latest file in folder
# TYPE s3_latest_file_timestamp gauge
s3_latest_file_timestamp{bucket="bucket-name",folder="backup"} 1519524066157.0
# HELP s3_oldest_file_timestamp Last modified timestamp(milliseconds) for oldest file in folder
# TYPE s3_oldest_file_timestamp gauge
s3_oldest_file_timestamp{bucket="bucket-name",folder="backup"} 1519005663854.0
# HELP s3_latest_file_size Size in bytes for latest file in folder
# TYPE s3_latest_file_size gauge
s3_latest_file_size{bucket="bucket-name",folder="backup"} 290355072.0
# HELP s3_oldest_file_size Size in bytes for latest file in folder
# TYPE s3_oldest_file_size gauge
s3_oldest_file_size{bucket="bucket-name",folder="backup"} 281699347.0
# HELP s3_file_count Numbeer of existing files in folder
# TYPE s3_file_count gauge
s3_file_count{bucket="bucket-name", folder="backup"} 7.0
# HELP s3_success Displays whether or not the listing of S3 was a success
# TYPE s3_success gauge
s3_success{bucket="bucket-name",folder="backup"} 1.0
```

## Alert Example

* Alert for time of latest backup. This example checks if backup is created every day (< 30h)

```
groups:
- name: host.rules
  rules:
  - alert: backup_is_too_old
    expr: (time()) - s3_latest_file_timestamp > 108000
    for: 5m
    labels:
      severity: critical
    annotations:
      description: Backup too old. Reported by instance {{ $labels.instance }}.
      summary: Backup too old


```

* Alert for size of latest backup. This example checks latest backup file created has minimum size of 1MB

```
  - alert: backup_size_is_too_small
    expr: s3_latest_file_size < 1000000
    for: 5m
    labels:
      severity: critical
    annotations:
      description: Backup size too small. Reported by instance {{ $labels.instance }}.
      summary: Backup size too small
```

## Run

### Using code (local)

```sh
pip install -r app/requirements.txt
aws-profile -p prod/vault python app/exporter.py config/config.yml
```

### Using docker

```
docker run -p 9327:9327 -v ./config:/config jamotion/s3-exporter
```

### Using docker-compose

Currently the code will not be reloaded when it changes, so run the container
interactively:

```
docker-compose run --service-ports s3
```

Then run the Python exporter process:

```
python exporter.py /config/config.yml
```
