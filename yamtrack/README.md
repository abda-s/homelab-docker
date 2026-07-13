# Yamtrack

Self-hosted media tracker for movies, TV shows, anime, manga, video games, books, comics, and board games.

- Source: https://github.com/FuzzyGrim/Yamtrack
- Docs: https://fuzzygrim.github.io/Yamtrack/

## Quick Start

cd ~/docker-homelab/yamtrack
docker compose up -d

Access at: http://localhost:8000

## Files

- docker-compose.yml - Compose definition
- .env - Environment variables (SECRET, TZ, etc.)
- db/ - SQLite database directory (created on first run)

## Updating

cd ~/docker-homelab/yamtrack
docker compose pull
docker compose up -d
