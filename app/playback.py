import logging

import requests

LOGGER = logging.getLogger(__name__)

_PLAYBACK_SQL = (
    'SELECT UserName, ItemId, ItemType, SUM(PlayDuration) AS TotalSeconds '
    'FROM PlaybackActivity '
    'GROUP BY UserName, ItemId, ItemType'
)


def fetch_playback_rows(api_url: str, api_key: str) -> list:
    """Return one dict per (user, item, type) with cumulative seconds watched."""
    url = f'{api_url}/user_usage_stats/submit_custom_query?api_key={api_key}'
    body = {'CustomQueryString': _PLAYBACK_SQL, 'ReplaceUserId': True}
    response = requests.post(url, json=body)
    response.raise_for_status()
    data = response.json()
    # The plugin spells the key 'colums' (not 'columns')
    columns = data['colums']
    return [dict(zip(columns, row)) for row in data['results']]


def fetch_item_details(api_url: str, api_key: str, item_id: str, cache: dict) -> dict:
    """Return genres and series name for a Jellyfin item, reading from cache when available."""
    if item_id in cache:
        return cache[item_id]
    url = f'{api_url}/Items/{item_id}?Fields=Genres,SeriesName&api_key={api_key}'
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    details = {
        'Genres': data.get('Genres', []),
        'SeriesName': data.get('SeriesName'),
    }
    cache[item_id] = details
    return details


def update_playback_metrics(
    api_url: str,
    api_key: str,
    watch_time_gauge,
    series_gauge,
    genre_gauge,
    item_cache: dict,
) -> None:
    """Clear and repopulate all three playback gauges from current Playback Reporting data."""
    rows = fetch_playback_rows(api_url, api_key)

    watch_time_totals = {}
    series_totals = {}
    genre_totals = {}

    for row in rows:
        user = row['UserName']
        item_id = row['ItemId']
        media_type = row['ItemType']
        seconds = row['TotalSeconds']

        key = (user, media_type)
        watch_time_totals[key] = watch_time_totals.get(key, 0) + seconds

        try:
            details = fetch_item_details(api_url, api_key, item_id, item_cache)
        except Exception as e:
            LOGGER.warning(f'Could not fetch details for item {item_id}: {e}')
            details = {'Genres': [], 'SeriesName': None}

        series_name = details.get('SeriesName')
        if series_name:
            key = (user, series_name)
            series_totals[key] = series_totals.get(key, 0) + seconds

        for genre in details.get('Genres', []):
            key = (user, genre)
            genre_totals[key] = genre_totals.get(key, 0) + seconds

    watch_time_gauge.clear()
    for (user, media_type), total in watch_time_totals.items():
        watch_time_gauge.labels(user=user, media_type=media_type).set(total)

    series_gauge.clear()
    for (user, series), total in series_totals.items():
        series_gauge.labels(user=user, series=series).set(total)

    genre_gauge.clear()
    for (user, genre), total in genre_totals.items():
        genre_gauge.labels(user=user, genre=genre).set(total)
