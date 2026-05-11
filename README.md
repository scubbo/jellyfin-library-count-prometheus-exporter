# jellyfin-library-count-prometheus-exporter

Prometheus exporter for Jellyfin. Exposes library counts and per-user playback watch-time metrics.

## Metrics

### Library counts

| Metric | Description |
|--------|-------------|
| `jellyfin_MovieCount` | Number of movies |
| `jellyfin_SeriesCount` | Number of series |
| `jellyfin_EpisodeCount` | Number of episodes |
| `jellyfin_SongCount` | Number of songs |
| `jellyfin_AlbumCount` | Number of albums |
| `jellyfin_ArtistCount` | Number of artists |
| *(+ others)* | See `MEDIA_TYPES` in `main.py` |

### Playback watch time

Requires the [Playback Reporting plugin](https://github.com/jellyfin/jellyfin-plugin-playbackreporting) to be installed in Jellyfin.

| Metric | Labels | Description |
|--------|--------|-------------|
| `jellyfin_playback_watch_time_seconds` | `user`, `media_type` | Cumulative seconds watched per user per media type |
| `jellyfin_playback_series_watch_time_seconds` | `user`, `series` | Cumulative seconds of episodes watched per user per series |
| `jellyfin_playback_genre_watch_time_seconds` | `user`, `genre` | Cumulative seconds watched per user per genre (time split evenly across an item's genres) |

## Configuration

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `API_URL` | *(required)* | Base URL of the Jellyfin instance |
| `API_KEY` | *(required)* | Jellyfin API key (admin) |
| `REFRESH_RATE` | `60` | Seconds between metric refreshes |
| `LOG_LEVEL` | `INFO` | Python log level |

## Running

```
docker run -p 8555:8555 \
  -e API_URL=http://jellyfin:8096 \
  -e API_KEY=your-api-key \
  ghcr.io/scubbo/jellyfin-library-count-prometheus-exporter:latest
```

Metrics are served at `:8555/metrics`.

## Development

```
pip install -r app/requirements.txt -r requirements-dev.txt
python3 -m pytest tests/
```
