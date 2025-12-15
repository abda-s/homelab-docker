# My Homelab Docker Setup

This repository contains the Docker Compose configurations for my personal homelab. It's a collection of self-hosted services designed to provide functionality for media management, home automation, network-wide ad-blocking, and photo storage.

## Overview

Each subdirectory in this repository represents a distinct service or a stack of related services, managed by its own `docker-compose.yml` file.

### Services

*   [**DNS (Pi-hole)**](./dns/pi-hole/): A network-wide ad and tracker blocker. It acts as a local DNS server to filter out unwanted requests.
*   [**Immich**](./immich/): A self-hosted photo and video backup solution, providing a private alternative to Google Photos.
*   [**Media Stack**](./media/): A comprehensive suite of applications for managing and streaming media, including Jellyfin, the *Arr suite, and qBittorrent.
*   [**Smarthome (Home Assistant)**](./smarthome/): A powerful home automation platform for controlling smart devices and creating automations.

## Service Ports

Below is a summary of the primary web interface ports for the services in this homelab setup.

| Service           | Stack       | Port   | URL                          |
| :---------------- | :---------- | :----- | :--------------------------- |
| Pi-hole           | `dns`       | `8085` | `http://<host-ip>:8085`      |
| Home Assistant    | `smarthome` | `8123` | `http://<host-ip>:8123`      |
| Immich            | `immich`    | `2283` | `http://<host-ip>:2283`      |
| Jellyfin          | `media`     | `8096` | `http://<host-ip>:8096`      |
| qBittorrent       | `media`     | `8080` | `http://<host-ip>:8080`      |
| Prowlarr          | `media`     | `9696` | `http://<host-ip>:9696`      |
| Sonarr            | `media`     | `8989` | `http://<host-ip>:8989`      |
| Radarr            | `media`     | `7878` | `http://<host-ip>:7878`      |
| Bazarr            | `media`     | `6767` | `http://<host-ip>:6767`      |

*Note: Home Assistant runs in `host` network mode, so it directly uses port `8123` on the host machine.*

## Structure

Each service is isolated in its own directory to keep the configurations clean and independent. Refer to the `README.md` file within each subdirectory for detailed setup and usage instructions.

## General Usage

1.  Navigate to the directory of the service you want to run (e.g., `cd media`).
2.  If required, create and configure the `.env` file as described in the service's `README.md`.
3.  Start the services using Docker Compose:
    ```bash
    docker compose up -d
    ```
4.  To stop the services, run:
    ```bash
    docker compose down
    ```
