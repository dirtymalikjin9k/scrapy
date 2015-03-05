# -*- coding: utf-8 -*-

import os
import sys
import logging
from logging.config import dictConfig

from twisted.python.failure import Failure
from twisted.python import log as twisted_log

import scrapy
from scrapy.settings import overridden_settings

logger = logging.getLogger('scrapy')


class FailureFormatter(logging.Filter):
    """Extract exc_info from Failure instances provided as contextual data

    This filter mimics Twisted log.err formatting for its first `_stuff`
    argument, which means that reprs of non Failure objects are appended to the
    log messages.
    """

    def filter(self, record):
        failure = record.__dict__.get('failure')
        if failure:
            if isinstance(failure, Failure):
                record.exc_info = (failure.type, failure.value, failure.tb)
            else:
                record.msg += os.linesep + repr(failure)
        return True


DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'failure_formatter': {
            '()': 'scrapy.utils.log.FailureFormatter',
        },
    },
    'loggers': {
        'scrapy': {
            'level': 'DEBUG',
            'filters': ['failure_formatter'],
        },
        'twisted': {
            'level': 'ERROR',
        },
    }
}


def configure_logging(settings=None):
    """Initialize and configure default loggers

    This function does:
      - Route warnings and twisted logging through Python standard logging
      - Set FailureFormatter filter on Scrapy logger
      - Assign DEBUG and ERROR level to Scrapy and Twisted loggers respectively
      - Create a handler for the root logger according to given settings
    """
    if not sys.warnoptions:
        # Route warnings through python logging
        logging.captureWarnings(True)

    observer = twisted_log.PythonLoggingObserver('twisted')
    observer.start()

    dictConfig(DEFAULT_LOGGING)
    if settings:
        logging.root.setLevel(logging.NOTSET)

        if settings.getbool('LOG_STDOUT'):
            sys.stdout = StreamLogger(logging.getLogger('stdout'))

        # Set up the default log handler
        filename = settings.get('LOG_FILE')
        if filename:
            encoding = settings.get('LOG_ENCODING')
            handler = logging.FileHandler(filename, encoding=encoding)
        elif settings.getbool('LOG_ENABLED'):
            handler = logging.StreamHandler()
        else:
            handler = logging.NullHandler()

        formatter = logging.Formatter(
            fmt=settings.get('LOG_FORMAT'),
            datefmt=settings.get('LOG_DATEFORMAT')
        )
        handler.setFormatter(formatter)
        handler.setLevel(settings.get('LOG_LEVEL'))
        logging.root.addHandler(handler)


def log_scrapy_info(settings):
    logger.info("Scrapy %(version)s started (bot: %(bot)s)",
                {'version': scrapy.__version__, 'bot': settings['BOT_NAME']})

    logger.info("Optional features available: %(features)s",
                {'features': ", ".join(scrapy.optional_features)})

    d = dict(overridden_settings(settings))
    logger.info("Overridden settings: %(settings)r", {'settings': d})


class StreamLogger(object):
    """Fake file-like stream object that redirects writes to a logger instance

    Taken from:
        http://www.electricmonk.nl/log/2011/08/14/redirect-stdout-and-stderr-to-a-logger-in-python/
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


class LogCounterHandler(logging.Handler):
    """Record log levels count into a crawler stats"""

    def __init__(self, crawler, *args, **kwargs):
        super(LogCounterHandler, self).__init__(*args, **kwargs)
        self.crawler = crawler

    def emit(self, record):
        sname = 'log_count/{}'.format(record.levelname)
        self.crawler.stats.inc_value(sname)
