import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import responses
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from playback import fetch_playback_rows, fetch_item_details, update_playback_metrics

API_URL = 'http://jellyfin.test'
API_KEY = 'test-key'

PLAYBACK_SQL_URL = f'{API_URL}/user_usage_stats/submit_custom_query'


def _make_gauges():
    registry = CollectorRegistry()
    return (
        Gauge('jellyfin_playback_watch_time_seconds', 'Watch time by user and media type',
              ['user', 'media_type'], registry=registry),
        Gauge('jellyfin_playback_series_watch_time_seconds', 'Watch time by user and series',
              ['user', 'series'], registry=registry),
        Gauge('jellyfin_playback_genre_watch_time_seconds', 'Watch time by user and genre',
              ['user', 'genre'], registry=registry),
        registry,
    )


def _sql_response(rows):
    return {
        'colums': ['UserName', 'ItemId', 'ItemType', 'TotalSeconds'],
        'results': rows,
    }


# --- fetch_playback_rows ---

@responses.activate
def test_fetch_playback_rows_returns_structured_rows():
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([
        ['alice', 'item-1', 'Movie', 3600],
        ['bob', 'item-2', 'Episode', 1800],
    ]))
    rows = fetch_playback_rows(API_URL, API_KEY)
    assert rows == [
        {'UserName': 'alice', 'ItemId': 'item-1', 'ItemType': 'Movie', 'TotalSeconds': 3600},
        {'UserName': 'bob', 'ItemId': 'item-2', 'ItemType': 'Episode', 'TotalSeconds': 1800},
    ]


@responses.activate
def test_fetch_playback_rows_sends_replace_user_id_and_sql():
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([]))
    fetch_playback_rows(API_URL, API_KEY)
    body = json.loads(responses.calls[0].request.body)
    assert body['ReplaceUserId'] is True
    assert 'PlaybackActivity' in body['CustomQueryString']
    # DB column is UserId; ReplaceUserId renames it to UserName in the output
    assert 'UserId' in body['CustomQueryString']


@responses.activate
def test_fetch_playback_rows_empty_returns_empty_list():
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([]))
    assert fetch_playback_rows(API_URL, API_KEY) == []


# --- fetch_item_details ---

@responses.activate
def test_fetch_item_details_returns_genres_and_series():
    responses.add(responses.GET, f'{API_URL}/Items/item-1',
                  json={'Genres': ['Action', 'Drama'], 'SeriesName': None})
    details = fetch_item_details(API_URL, API_KEY, 'item-1', {})
    assert details == {'Genres': ['Action', 'Drama'], 'SeriesName': None}


@responses.activate
def test_fetch_item_details_returns_series_name_for_episodes():
    responses.add(responses.GET, f'{API_URL}/Items/ep-1',
                  json={'Genres': ['Comedy'], 'SeriesName': 'Severance'})
    details = fetch_item_details(API_URL, API_KEY, 'ep-1', {})
    assert details['SeriesName'] == 'Severance'


@responses.activate
def test_fetch_item_details_caches_result():
    responses.add(responses.GET, f'{API_URL}/Items/item-1',
                  json={'Genres': ['Action'], 'SeriesName': None})
    cache = {}
    fetch_item_details(API_URL, API_KEY, 'item-1', cache)
    fetch_item_details(API_URL, API_KEY, 'item-1', cache)
    assert len(responses.calls) == 1


@responses.activate
def test_fetch_item_details_populates_cache():
    responses.add(responses.GET, f'{API_URL}/Items/item-1',
                  json={'Genres': ['Horror'], 'SeriesName': None})
    cache = {}
    fetch_item_details(API_URL, API_KEY, 'item-1', cache)
    assert 'item-1' in cache


# --- update_playback_metrics ---

@responses.activate
def test_update_watch_time_by_media_type():
    watch_gauge, series_gauge, genre_gauge, registry = _make_gauges()
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([
        ['alice', 'item-1', 'Movie', 3600],
        ['alice', 'item-2', 'Movie', 1800],
        ['bob',   'item-3', 'Episode', 900],
    ]))
    responses.add(responses.GET, f'{API_URL}/Items/item-1', json={'Genres': [], 'SeriesName': None})
    responses.add(responses.GET, f'{API_URL}/Items/item-2', json={'Genres': [], 'SeriesName': None})
    responses.add(responses.GET, f'{API_URL}/Items/item-3', json={'Genres': [], 'SeriesName': None})

    update_playback_metrics(API_URL, API_KEY, watch_gauge, series_gauge, genre_gauge, {})

    output = generate_latest(registry).decode('utf-8')
    assert 'jellyfin_playback_watch_time_seconds{media_type="Movie",user="alice"} 5400.0' in output
    assert 'jellyfin_playback_watch_time_seconds{media_type="Episode",user="bob"} 900.0' in output


@responses.activate
def test_update_series_watch_time():
    watch_gauge, series_gauge, genre_gauge, registry = _make_gauges()
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([
        ['alice', 'ep-1', 'Episode', 2400],
        ['alice', 'ep-2', 'Episode', 1200],
    ]))
    responses.add(responses.GET, f'{API_URL}/Items/ep-1',
                  json={'Genres': ['Drama'], 'SeriesName': 'Severance'})
    responses.add(responses.GET, f'{API_URL}/Items/ep-2',
                  json={'Genres': ['Drama'], 'SeriesName': 'Severance'})

    update_playback_metrics(API_URL, API_KEY, watch_gauge, series_gauge, genre_gauge, {})

    output = generate_latest(registry).decode('utf-8')
    assert 'jellyfin_playback_series_watch_time_seconds{series="Severance",user="alice"} 3600.0' in output


@responses.activate
def test_update_genre_watch_time():
    watch_gauge, series_gauge, genre_gauge, registry = _make_gauges()
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([
        ['alice', 'ep-1', 'Episode', 2400],
        ['alice', 'ep-2', 'Episode', 1200],
    ]))
    responses.add(responses.GET, f'{API_URL}/Items/ep-1',
                  json={'Genres': ['Drama'], 'SeriesName': 'Severance'})
    responses.add(responses.GET, f'{API_URL}/Items/ep-2',
                  json={'Genres': ['Drama'], 'SeriesName': 'Severance'})

    update_playback_metrics(API_URL, API_KEY, watch_gauge, series_gauge, genre_gauge, {})

    output = generate_latest(registry).decode('utf-8')
    assert 'jellyfin_playback_genre_watch_time_seconds{genre="Drama",user="alice"} 3600.0' in output


@responses.activate
def test_update_aggregates_multiple_genres():
    watch_gauge, series_gauge, genre_gauge, registry = _make_gauges()
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([
        ['alice', 'item-1', 'Movie', 3600],
    ]))
    responses.add(responses.GET, f'{API_URL}/Items/item-1',
                  json={'Genres': ['Action', 'Thriller'], 'SeriesName': None})

    update_playback_metrics(API_URL, API_KEY, watch_gauge, series_gauge, genre_gauge, {})

    output = generate_latest(registry).decode('utf-8')
    assert 'jellyfin_playback_genre_watch_time_seconds{genre="Action",user="alice"} 3600.0' in output
    assert 'jellyfin_playback_genre_watch_time_seconds{genre="Thriller",user="alice"} 3600.0' in output


@responses.activate
def test_update_uses_item_cache():
    watch_gauge, series_gauge, genre_gauge, registry = _make_gauges()
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([
        ['alice', 'item-1', 'Movie', 1000],
        ['bob',   'item-1', 'Movie', 2000],
    ]))
    responses.add(responses.GET, f'{API_URL}/Items/item-1',
                  json={'Genres': ['Action'], 'SeriesName': None})

    update_playback_metrics(API_URL, API_KEY, watch_gauge, series_gauge, genre_gauge, {})

    item_calls = [c for c in responses.calls if '/Items/' in c.request.url]
    assert len(item_calls) == 1


@responses.activate
def test_update_skips_series_gauge_for_movies():
    watch_gauge, series_gauge, genre_gauge, registry = _make_gauges()
    responses.add(responses.POST, PLAYBACK_SQL_URL, json=_sql_response([
        ['alice', 'item-1', 'Movie', 3600],
    ]))
    responses.add(responses.GET, f'{API_URL}/Items/item-1',
                  json={'Genres': ['Action'], 'SeriesName': None})

    update_playback_metrics(API_URL, API_KEY, watch_gauge, series_gauge, genre_gauge, {})

    output = generate_latest(registry).decode('utf-8')
    # HELP/TYPE lines always appear; verify no labeled data points
    assert 'jellyfin_playback_series_watch_time_seconds{' not in output
