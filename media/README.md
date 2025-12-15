# Self-Hosted Media Server Stack

A simplified, Docker-based media server stack featuring Jellyfin, qBittorrent, and the full \*Arr suite (Sonarr, Radarr, Prowlarr, Bazarr).

## Features

*   **Media Server:** Jellyfin
*   **Download Client:** qBittorrent
*   **Automation:** Sonarr (TV), Radarr (Movies), Bazarr (Subtitles)
*   **Indexer Manager:** Prowlarr
*   **Static Networking:** Custom bridge network with assigned static IPs for stability.
*   **Hardware Acceleration:** Pre-configured for Intel Quick Sync (QSV) on Jellyfin.

## Prerequisites

Before running the stack, you must create a `.env` file in the same directory as your `compose.yaml`. This file defines the variables used for permissions and file paths.

### 1. Create the `.env` file

Create a file named `.env` and paste the following. Change the values to match your specific setup:

```bash
# User and Group IDs (Run 'id' in your terminal to find yours)
PUID=1000
PGID=1000

# Timezone
TZ=America/New_York

# The path on your Host machine where media/downloads are stored
MEDIA_PATH=/home/user/media_server/data
```

### 2. Directory Structure & Permissions

To ensure hardlinks work (instant moves instead of copying files) and to keep file management simple, we use a single volume mount point `/data`.

On your host machine (at the location defined in `MEDIA_PATH`), your folder structure should look like this:

```text
data
├── torrents
│   ├── qbittorrent
│   │   ├── completed
│   │   ├── incomplete
│   │   └── torrents
├── media
│   ├── movies
│   ├── tv
```

**Set Permissions:**
To prevent "Permission Denied" errors, ensure your host directories are owned by the user defined in your PUID/PGID:

```bash
sudo chown -R 1000:1000 /path/to/your/data
```

## Installation

1.  Place your `compose.yaml` and `.env` files in a directory.
2.  Run the stack:
    ```bash
    docker compose up -d
    ```

## Service Overview & Access

This stack uses a custom bridge network (`medianetwork`) with the subnet `172.40.0.0/24`.

| Service       | App URL                 | Static IP     | Description     | Notes                                                              |
| :------------ | :---------------------- | :------------ | :-------------- | :----------------------------------------------------------------- |
| **Jellyfin**  | `http://localhost:8096` | `172.40.0.10` | Media Server    | Configured for Intel Quick Sync (QSV) hardware acceleration.       |
| **qBittorrent** | `http://localhost:8080` | `172.40.0.14` | Torrent Client  | **Warning:** Not configured with a VPN.                            |
| **Prowlarr**  | `http://localhost:9696` | `172.40.0.16` | Indexer Manager |                                                                    |
| **Sonarr**    | `http://localhost:8989` | `172.40.0.17` | TV Shows        |                                                                    |
| **Radarr**    | `http://localhost:7878` | `172.40.0.18` | Movies          |                                                                    |
| **Bazarr**    | `http://localhost:6767` | `172.40.0.20` | Subtitles       |                                                                    |

## Configuration Guide

### 1. qBittorrent Setup

*   **Login:** The default login is usually `admin` / `adminadmin` (check logs if random password is generated: `docker logs qbittorrent`).
*   **Download Paths:** Go to *Tools > Options > Downloads*. Map the paths to the internal container structure:
    *   **Default Save Path:** `/data/torrents/qbittorrent/completed`
    *   **Keep incomplete torrents in:** `/data/torrents/qbittorrent/incomplete`
    *   **Copy .torrent files to:** `/data/torrents/qbittorrent/torrents`

> [!WARNING]
> This docker compose configuration **does not** include a VPN container (Gluetun). Your IP address will be visible when downloading torrents. Ensure you are using a proxy within qBittorrent or are aware of the privacy risks.

### 2. Connecting Apps (*Arr to Clients)

Because we are using a custom network with static IPs, configuration is straightforward.

**Adding Download Client (in Sonarr/Radarr):**

*   **Host:** `172.40.0.14` (or use the container name `qbittorrent`)
*   **Port:** `8080`

**Adding Prowlarr to Sonarr/Radarr:**

*   **Host:** `172.40.0.16` (or use the container name `prowlarr`)
*   **Port:** `9696`

### 3. Path Mapping (Root Folder)

When setting up Sonarr/Radarr, when asked for the **Root Folder** for your media, always select the path inside `/data`.

*   Movies Root: `/data/media/movies`
*   TV Root: `/data/media/tv`

## Troubleshooting

**Permissions Errors:**
If the apps cannot write to the folders, ensure the `PUID` and `PGID` in your `.env` file match the user who owns the folders on the host machine.

**Networking:**
If containers cannot talk to each other, ensure they are all running on the `medianetwork`. You can check this by running:

```bash
docker network inspect medianetwork
```