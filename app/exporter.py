# !/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Jamotion GmbH, Your Odoo implementation partner
#    Copyright (C) 2004-2010 Jamotion GmbH.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    Created by renzo on 23.02.18.
#
import argparse
import fnmatch
import logging
import time

import boto3
import botocore.exceptions
import yaml
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

DEFAULT_PORT = 9327
DEFAULT_LOG_LEVEL = 'info'


class S3Collector(object):
    def __init__(self, config):
        self._config = config
        access_key = config.get('access_key', False)
        secret_key = config.get('secret_key', False)
        if access_key and secret_key:
            self._client = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key)
        else:
            self._client = boto3.client('s3')

    def collect(self):
        pattern = self._config.get('pattern', False)
            
        latest_file_timestamp_gauge = GaugeMetricFamily(
                's3_latest_file_timestamp',
                'Last modified timestamp(milliseconds) for latest file in '
                'folder',
                labels=['folder', 'bucket'],
        )
        oldest_file_timestamp_gauge = GaugeMetricFamily(
                's3_oldest_file_timestamp',
                'Last modified timestamp(milliseconds) for oldest file in '
                'folder',
                labels=['folder', 'bucket'],
        )
        latest_file_size_gauge = GaugeMetricFamily(
                's3_latest_file_size',
                'Size in bytes for latest file in folder',
                labels=['folder', 'bucket'],
        )
        oldest_file_size_gauge = GaugeMetricFamily(
                's3_oldest_file_size',
                'Size in bytes for latest file in folder',
                labels=['folder', 'bucket'],
        )
        file_count_gauge = GaugeMetricFamily(
                's3_file_count',
                'Number of existing files in folder',
                labels=['folder', 'bucket'],
        )
        success_gauge = GaugeMetricFamily(
                's3_success',
                'Displays whether or not the listing of S3 was a success',
                labels=['folder', 'bucket'],
        )

        success = True

        for folder in config.get('folders'):
            bucket = config.get('bucket')

            if folder == '':
                prefix = None
            else:
                prefix = folder[-1] == '/' and folder or '{0}/'.format(folder)

            logging.debug('Listing contents of bucket: "{0}" with prefix: "{1}"'.format(bucket, prefix))

            try:
                if prefix == None or prefix == '/':
                    result = self._client.list_objects_v2(Bucket=bucket)
                else:
                    result = self._client.list_objects_v2(Bucket=bucket,
                                                          Prefix=prefix)

            except botocore.exceptions.ClientError as err:
                success = False
                logging.error('Error listing contents of bucket: "{0}" with prefix: "{1}" error: "{2}"'.format(bucket, prefix, err))
                continue

            if 'Contents' in result:
                files = result['Contents']
            else:
                success = False
                logging.error('Error not content found in bucket: "{0}" with prefix: "{1}"'.format(bucket, prefix))
                continue

            if pattern:
                files = [f for f in files if fnmatch.fnmatch(f['Key'], pattern)]
            files = sorted(files, key=lambda s: s['LastModified'])
            if not files:
                continue

            last_file = files[-1]
            last_file_name = last_file['Key']
            oldest_file = files[0]
            oldest_file_name = oldest_file['Key']
            latest_modified = last_file['LastModified'].timestamp()
            oldest_modified = oldest_file['LastModified'].timestamp()

            file_count_gauge.add_metric([
                folder,
                bucket
            ], len(files))
            
            latest_file_timestamp_gauge.add_metric([
                folder,
                bucket
            ], latest_modified)
            oldest_file_timestamp_gauge.add_metric([
                folder,
                bucket
            ], oldest_modified)
            latest_file_size_gauge.add_metric([
                folder,
                bucket
            ], int(last_file['Size']))
            oldest_file_size_gauge.add_metric([
                folder,
                bucket
            ], int(oldest_file['Size']))
            
        success_gauge.add_metric([
            folder,
            bucket
        ], int(success))

        yield latest_file_timestamp_gauge
        yield oldest_file_timestamp_gauge
        yield latest_file_size_gauge
        yield oldest_file_size_gauge
        yield file_count_gauge
        yield success_gauge


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description='Expose metrics for S3 storage')
    parser.add_argument('config_file_path', help='Path of the config file')
    args = parser.parse_args()
    with open(args.config_file_path) as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
        log_level = config.get('log_level', DEFAULT_LOG_LEVEL)
        logging.basicConfig(
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                level=logging.getLevelName(log_level.upper()))
        exporter_port = config.get('exporter_port', DEFAULT_PORT)
        logging.debug("Config %s", config)
        logging.info('Starting server on port %s', exporter_port)
        start_http_server(exporter_port)
        REGISTRY.register(S3Collector(config))
    while True: time.sleep(1)
