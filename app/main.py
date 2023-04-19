#!/usr/bin/env python3

import datetime
import json
import logging
import os
import sys
import time

import requests
from functools import partial

from prometheus_client import start_http_server, Gauge, REGISTRY, GC_COLLECTOR, PLATFORM_COLLECTOR, PROCESS_COLLECTOR

REGISTRY.unregister(GC_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)
REGISTRY.unregister(PROCESS_COLLECTOR)


MEDIA_TYPES = ['Movie', 'Series', 'Episode', 'Artist', 'Program', 'Trailer', 'Song', 'Album', 'MusicVideo','BoxSet', 'Book', 'Item']

CACHE_LAST_QUERIED = datetime.datetime.fromtimestamp(0)
CACHE = {}

logging.basicConfig(
	level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO')),
	stream=sys.stdout,
	format='%(asctime)s %(levelname)s %(message)s')
LOGGER = logging.getLogger(__name__)


def _refresh_cache():
	LOGGER.info('Refreshing cache')
	full_url = f'{os.environ["API_URL"]}/Items/Counts?api_key={os.environ["API_KEY"]}'
	LOGGER.debug(f'{full_url=}')
	global CACHE
	CACHE = requests.get(full_url).json()
	LOGGER.debug(f'Refreshed cache with {CACHE}')
	global CACHE_LAST_QUERIED
	CACHE_LAST_QUERIED = datetime.datetime.now()

def _fetch_value_from_cache(media_type):
	# Should refresh?
	if (not CACHE) or ((datetime.datetime.now()-CACHE_LAST_QUERIED).seconds >= os.environ.get('REFRESH_RATE', 60)):
		_refresh_cache()
	return CACHE[media_type+'Count']


def _get_value(media_type):
	return _fetch_value_from_cache(media_type)
	return [media_type+'Count']


def _gauge_update(media_type):
	return partial(_get_value, media_type=media_type)


def main():
	gauges = {media_type: Gauge(f'jellyfin_{media_type}Count', f'Count of {media_type}') for media_type in MEDIA_TYPES}
	for media_type, gauge in gauges.items():
		# Slightly inefficient that each Gauge will query
		# independently rather than updating a 
		gauge.set_function(_gauge_update(media_type))
	start_http_server(8555)
	LOGGER.info('Starting up!')
	while True:
		time.sleep(1)


if __name__ == '__main__':
	main()