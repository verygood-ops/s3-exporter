# !/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Jamotion GmbH, Your Odoo implementation partner
#    Copyright (C) 2004-2010 Jamotion GmbH.
#    Copyright (C) 2021 Very Good Security, Inc.
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
import datetime
import fnmatch
import logging
import re
import time

import boto3
import botocore.exceptions
import dateparser
import yaml
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

DEFAULT_PORT = 9327
DEFAULT_LOG_LEVEL = 'debug'


def to_seconds(date):
    return time.mktime(date.timetuple())


class S3Collector(object):

    def __init__(self, config):
        self._config = config
        access_key = config.get('access_key', False)
        secret_key = config.get('secret_key', False)
        endpoint_url = config.get('host_base', False)
        verify = config.get('use_https', True)

        if access_key and secret_key:
            self._client = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    endpoint_url=endpoint_url,
                    verify=verify)
        else:
            self._client = boto3.client('s3')

    def collect(self):
        patterns = self._config.get('patterns', ["*"])
        if not isinstance(patterns, list):
            patterns = [patterns, ]
        smart_folder_date = self._config.get('smart_folder_date', False)
        smart_pattern_date = self._config.get('smart_pattern_date', False)
        if smart_pattern_date or smart_folder_date:
            base_date = dateparser.parse(self._config.get('base_date', 'today'))

        latest_file_timestamp_gauge = GaugeMetricFamily(
                's3_latest_file_timestamp',
                'Last modified timestamp(milliseconds) for latest file in '
                'folder',
                labels=['folder', 'file'],
        )
        oldest_file_timestamp_gauge = GaugeMetricFamily(
                's3_oldest_file_timestamp',
                'Last modified timestamp(milliseconds) for oldest file in '
                'folder',
                labels=['folder', 'file'],
        )
        latest_file_size_gauge = GaugeMetricFamily(
                's3_latest_file_size',
                'Size in bytes for latest file in folder',
                labels=['folder', 'file'],
        )
        oldest_file_size_gauge = GaugeMetricFamily(
                's3_oldest_file_size',
                'Size in bytes for latest file in folder',
                labels=['folder', 'file'],
        )
        file_count_gauge = GaugeMetricFamily(
                's3_file_count',
                'Number of existing files in folder',
                labels=['folder', 'file'],
        )
        success_gauge = GaugeMetricFamily(
                's3_success',
                'Displays whether or not the listing of S3 was a success',
                labels=['folder'],
        )

        success = True

        for folder in config.get('folders'):
            bucket = config.get('bucket')

            if folder == '':
                prefix = None
            else:
                prefix = folder[-1] == '/' and folder or '{0}/'.format(folder)

            if smart_folder_date:
                prefix = datetime.datetime.strftime(base_date, prefix)

            if prefix.endswith('/*/'):
                prefix = re.sub(r'(.*)\/\*\/$', r'\1', prefix)

            logging.debug('Listing contents of bucket: "{0}" with prefix: "{1}"'.format(bucket, prefix))
            token = None
            found_files = []
            while True:

                try:
                    kw = {
                        'Bucket': bucket,
                    }
                    if prefix and prefix != "/":
                        kw.update({'Prefix': prefix})
                    if token:
                        kw.update({'ContinuationToken': token})
                    result = self._client.list_objects_v2(**kw)
                except botocore.exceptions.ClientError as err:
                    success = False
                    logging.error('Error listing contents of bucket: "{0}" with prefix: "{1}" error: "{2}"'.format(bucket, prefix, err))
                    continue

                if 'Contents' in result:
                    found_files += result['Contents']
                    if result['IsTruncated']:
                        token = result['NextContinuationToken']
                        continue
                    else:
                        break
                else:
                    success = False
                    logging.error('Error no content found in bucket: "{0}" with prefix: "{1}"'.format(bucket, prefix))
                    break
            for pattern in patterns:
                if smart_pattern_date:
                    pattern = datetime.datetime.strftime(base_date, pattern)
                files = [f for f in found_files if fnmatch.fnmatch(f['Key'], pattern)]
                files = sorted(files, key=lambda s: s['LastModified'])
                if not files:
                    continue
                last_file = files[-1]
                last_file_name = last_file['Key']
                oldest_file = files[0]
                oldest_file_name = oldest_file['Key']
                latest_modified = to_seconds(last_file['LastModified'])
                oldest_modified = to_seconds(oldest_file['LastModified'])

                file_count_gauge.add_metric([
                    folder,
                    last_file_name
                ], len(files))

                latest_file_timestamp_gauge.add_metric([
                    folder,
                    last_file_name
                ], latest_modified)
                oldest_file_timestamp_gauge.add_metric([
                    folder,
                    last_file_name
                ], oldest_modified)
                latest_file_size_gauge.add_metric([
                    folder,
                    last_file_name
                ], int(last_file['Size']))
                oldest_file_size_gauge.add_metric([
                    folder,
                    oldest_file_name
                ], int(oldest_file['Size']))

                success_gauge.add_metric([
                    folder
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
        config = yaml.safe_load(config_file)
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
