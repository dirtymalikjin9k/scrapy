"""
This module contains some assorted functions used in tests
"""

import asyncio
import os
from posixpath import split
from unittest import mock

from importlib import import_module
from twisted.trial.unittest import SkipTest

from scrapy.exceptions import NotConfigured
from scrapy.utils.boto import is_botocore


def assert_aws_environ():
    """Asserts the current environment is suitable for running AWS testsi.
    Raises SkipTest with the reason if it's not.
    """
    skip_if_no_boto()
    if 'AWS_ACCESS_KEY_ID' not in os.environ:
        raise SkipTest("AWS keys not found")


def assert_gcs_environ():
    if 'GCS_PROJECT_ID' not in os.environ:
        raise SkipTest("GCS_PROJECT_ID not found")


def skip_if_no_boto():
    try:
        is_botocore()
    except NotConfigured as e:
        raise SkipTest(e)


def get_s3_content_and_delete(bucket, path, with_key=False):
    """ Get content from s3 key, and delete key afterwards.
    """
    if is_botocore():
        import botocore.session
        session = botocore.session.get_session()
        client = session.create_client('s3')
        key = client.get_object(Bucket=bucket, Key=path)
        content = key['Body'].read()
        client.delete_object(Bucket=bucket, Key=path)
    else:
        import boto
        # assuming boto=2.2.2
        bucket = boto.connect_s3().get_bucket(bucket, validate=False)
        key = bucket.get_key(path)
        content = key.get_contents_as_string()
        bucket.delete_key(path)
    return (content, key) if with_key else content


def get_gcs_content_and_delete(bucket, path):
    from google.cloud import storage
    client = storage.Client(project=os.environ.get('GCS_PROJECT_ID'))
    bucket = client.get_bucket(bucket)
    blob = bucket.get_blob(path)
    content = blob.download_as_string()
    acl = list(blob.acl)  # loads acl before it will be deleted
    bucket.delete_blob(path)
    return content, acl, blob


def get_ftp_content_and_delete(
        path, host, port, username,
        password, use_active_mode=False):
    from ftplib import FTP
    ftp = FTP()
    ftp.connect(host, port)
    ftp.login(username, password)
    if use_active_mode:
        ftp.set_pasv(False)
    ftp_data = []

    def buffer_data(data):
        ftp_data.append(data)
    ftp.retrbinary('RETR %s' % path, buffer_data)
    dirname, filename = split(path)
    ftp.cwd(dirname)
    ftp.delete(filename)
    return "".join(ftp_data)


def get_crawler(spidercls=None, settings_dict=None):
    """Return an unconfigured Crawler object. If settings_dict is given, it
    will be used to populate the crawler settings with a project level
    priority.
    """
    from scrapy.crawler import CrawlerRunner
    from scrapy.spiders import Spider

    runner = CrawlerRunner(settings_dict)
    return runner.create_crawler(spidercls or Spider)


def get_pythonpath():
    """Return a PYTHONPATH suitable to use in processes so that they find this
    installation of Scrapy"""
    scrapy_path = import_module('scrapy').__path__[0]
    return os.path.dirname(scrapy_path) + os.pathsep + os.environ.get('PYTHONPATH', '')


def get_testenv():
    """Return a OS environment dict suitable to fork processes that need to import
    this installation of Scrapy, instead of a system installed one.
    """
    env = os.environ.copy()
    env['PYTHONPATH'] = get_pythonpath()
    return env


def assert_samelines(testcase, text1, text2, msg=None):
    """Asserts text1 and text2 have the same lines, ignoring differences in
    line endings between platforms
    """
    testcase.assertEqual(text1.splitlines(), text2.splitlines(), msg)


def get_from_asyncio_queue(value):
    q = asyncio.Queue()
    getter = q.get()
    q.put_nowait(value)
    return getter


def mock_google_cloud_storage():
    """Creates autospec mocks for google-cloud-storage Client, Bucket and Blob
    classes and set their proper return values.
    """
    from google.cloud.storage import Client, Bucket, Blob
    client_mock = mock.create_autospec(Client)

    bucket_mock = mock.create_autospec(Bucket)
    client_mock.get_bucket.return_value = bucket_mock

    blob_mock = mock.create_autospec(Blob)
    bucket_mock.blob.return_value = blob_mock

    return (client_mock, bucket_mock, blob_mock)
