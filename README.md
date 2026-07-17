# My Homelab
This is my personal homelab setup. It is a collection of self-hosted services for photos, automation, and utilities.

Building this was a massive hassle. I spent way too much time fighting with Linux permissions, Docker volumes, and getting Apple devices to actually respect my local DNS. But it finally works, and it allows me to own my data instead of relying on big tech.

## Structure
*   [**Dashboard (Homarr)**](./core/dashboard/): A simple and powerful server dashboard.
*   [**DNS (Pi-hole)**](./dns/pi-hole/): A network-wide ad and tracker blocker. It acts as a local DNS server to filter out unwanted requests.
*   [**Immich**](./immich/): A self-hosted photo and video backup solution, providing a private alternative to Google Photos.
*   [**Smarthome (Home Assistant)**](./smarthome/): A powerful home automation platform for controlling smart devices and creating automations.
*   [**Faster Whisper**](./faster-whisper/): A robust, self-hosted implementation of OpenAI's Whisper model for local speech-to-text transcription. Features a custom worker with Voice Activity Detection (VAD), auto-resume for crashes, and smart queue management.
*   [**YTPTube**](./YTP/): A self-hosted YouTube downloader with a web interface.
*   [**Memos**](./memos/): A lightweight, self-hosted note-taking service.
*   [**Windows VM**](./windows/): A virtualized Windows 11 environment running via Docker, accessible remotely through RDP. Used for Windows-only applications.

## Service Overview

Here is a summary of the main services and their access points:

| Service | Stack | URL | Notes |
| :--- | :--- | :--- | :--- |
| Dashboard | `core` | `http://dashboard.elwahsh.home` | A simple, yet powerful dashboard for your server. |
| NGINX | `core` | `http://<subdomain>.elwahsh.home` | Reverse proxy for all other services. |
| Pi-hole | `dns` | `http://pihole.elwahsh.home` | Network-wide ad-blocker and DNS. |
| Home Assistant | `smarthome` | `http://ha.elwahsh.home` | Runs in `host` network mode. |
| ESPHome | `smarthome` | `http://esphome.elwahsh.home` | Runs in `host` network mode. |
| Immich | `immich` | `http://immich.elwahsh.home` | Photo and video backup. |
| YTPTube | `YTP` | `http://ytp.elwahsh.home` | YouTube downloader. |
| Memos | `memos` | `http://memos.elwahsh.home` | Note-taking service. |
| Windows VM | `windows` | RDP (port 3389) | Virtualized Windows 11 environment. |

*Note: Home Assistant and ESPHome run in `host` network mode, so they directly use ports `8123` and `6052` respectively on the host machine.*

## Removed Services

The following services were previously part of this homelab but have since been decommissioned:

*   **Media Stack** (media/): Jellyfin, Sonarr, Radarr, Prowlarr, qBittorrent, and Bazarr.
*   **Yamtrack** (yamtrack/): A self-hosted media tracker for movies, TV, anime, games, books, etc.

See the last version with all services at commit [`71bec19`](https://github.com/abda-s/homelab-docker/commit/71bec198ef53689d00769f0b5efb8ab4658cdcdc).

## Roadmap
There are still a few things I want to build when I have time:
- [x] **Server Dashboard**: A single landing page to monitor everything.
- [x] **Windows VM**: Virtualized Windows environment for remote access.
- [ ] **Minecraft Server**: For hosting my own world.
- [x] **AI Stack**: Setting up Ollama and Whisper servers locally. (Tried, but the hardware ain't good enough - didn't work out)
- [x] **"My Own Alexa"**: Integrating Home Assistant with Ollama, Whisper, and Piper to replace smart speakers with a local privacy-focused voice assistant. (Tried, but the hardware ain't good enough - didn't work out)
- [ ] **Laptop Backups**: An automated solution to backup my personal machine to the server.
- [ ] **Remote File Access**: A way to browse server files from anywhere (like Nextcloud or Filebrowser).

## Connecting to the Windows VM
To connect to the Windows VM from a Linux client, use FreeRDP:

```bash
flatpak run com.freerdp.FreeRDP \
  /v:<VM_IP>:3389 \
  /u:<username> \
  /p:<password> \
  /w:1920 /h:1080 \
  /dynamic-resolution \
  /sound \
  /clipboard \
  /drive:home,$HOME \
  /cert-ignore
```

*Note: Replace `<VM_IP>`, `<username>`, and `<password>` with your actual values. Store credentials securely and never commit them to this public repository.*

## Usage
1. Go to the service folder (e.g., `cd core`).
2. Check the `.env` file if needed.
3. Run it:
```bash
docker compose up -d
```
