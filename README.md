# My Homelab
This is my personal homelab setup. It is a collection of self-hosted services for media, automation, and backups.

Building this was a massive hassle. I spent way too much time fighting with Linux permissions, Docker volumes, and getting Apple devices to actually respect my local DNS. But it finally works, and it allows me to own my data instead of relying on big tech.

## Structure
*   [**Dashboard (Homarr)**](./core/dashboard/): A simple and powerful server dashboard.
*   [**DNS (Pi-hole)**](./dns/pi-hole/): A network-wide ad and tracker blocker. It acts as a local DNS server to filter out unwanted requests.
*   [**Immich**](./immich/): A self-hosted photo and video backup solution, providing a private alternative to Google Photos.
*   [**Media Stack**](./media/): A comprehensive suite of applications for managing and streaming media, including Jellyfin, the *Arr suite, and qBittorrent.
*   [**Smarthome (Home Assistant)**](./smarthome/): A powerful home automation platform for controlling smart devices and creating automations.
*   [**Faster Whisper**](./faster-whisper/): A robust, self-hosted implementation of OpenAI's Whisper model for local speech-to-text transcription. Features a custom worker with Voice Activity Detection (VAD), auto-resume for crashes, and smart queue management.
*   [**YTPTube**](./YTP/): A self-hosted YouTube downloader with a web interface.

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
| Jellyfin | `media` | `http://jellyfin.elwahsh.home` | Media server. |
| qBittorrent | `media` | `http://qbittorrent.elwahsh.home` | Torrent client. |
| Prowlarr | `media` | `http://prowlarr.elwahsh.home` | Indexer manager for the *Arrs. |
| Sonarr | `media` | `http://sonarr.elwahsh.home` | TV show automation. |
| Radarr | `media` | `http://radarr.elwahsh.home` | Movie automation. |
| Bazarr | `media` | `http://bazarr.elwahsh.home` | Subtitle automation. |
| YTPTube | `YTP` | `http://ytp.elwahsh.home` | YouTube downloader. |

*Note: Home Assistant and ESPHome run in `host` network mode, so they directly use ports `8123` and `6052` respectively on the host machine.*


## Roadmap
There are still a few things I want to build when I have time:
- [x] **Server Dashboard**: A single landing page to monitor everything.
- [ ] **Minecraft Server**: For hosting my own world.
- [ ] **AI Stack**: Setting up Ollama and Whisper servers locally.
- [ ] **"My Own Alexa"**: Integrating Home Assistant with Ollama, Whisper, and Piper to replace smart speakers with a local privacy-focused voice assistant.
- [ ] **Laptop Backups**: An automated solution to backup my personal machine to the server.
- [ ] **Remote File Access**: A way to browse server files from anywhere (like Nextcloud or Filebrowser).

## Usage
1. Go to the service folder (e.g., `cd media`).
2. Check the `.env` file if needed.
3. Run it:
```bash
docker compose up -d
```
