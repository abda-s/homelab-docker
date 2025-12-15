# My Homelab
This is my personal homelab setup. It is a collection of self-hosted services for media, automation, and backups.

Building this was a massive hassle. I spent way too much time fighting with Linux permissions, Docker volumes, and getting Apple devices to actually respect my local DNS. But it finally works, and it allows me to own my data instead of relying on big tech.

## Structure
*   [**DNS (Pi-hole)**](./dns/pi-hole/): A network-wide ad and tracker blocker. It acts as a local DNS server to filter out unwanted requests.
*   [**Immich**](./immich/): A self-hosted photo and video backup solution, providing a private alternative to Google Photos.
*   [**Media Stack**](./media/): A comprehensive suite of applications for managing and streaming media, including Jellyfin, the *Arr suite, and qBittorrent.
*   [**Smarthome (Home Assistant)**](./smarthome/): A powerful home automation platform for controlling smart devices and creating automations.

## Service Ports
Here is where everything lives on the network:

| Service | Stack | Port | URL |
| --- | --- | --- | --- |
| Pi-hole | `dns` | `8085` | `http://<host-ip>:8085` |
| Home Assistant | `smarthome` | `8123` | `http://<host-ip>:8123` |
| ESPHome | `smarthome` | `6052` | `http://<host-ip>:6052` |
| Immich | `immich` | `2283` | `http://<host-ip>:2283` |
| Jellyfin | `media` | `8096` | `http://<host-ip>:8096` |
| qBittorrent | `media` | `8080` | `http://<host-ip>:8080` |
| Prowlarr | `media` | `9696` | `http://<host-ip>:9696` |
| Sonarr | `media` | `8989` | `http://<host-ip>:8989` |
| Radarr | `media` | `7878` | `http://<host-ip>:7878` |
| Bazarr | `media` | `6767` | `http://<host-ip>:6767` |

*Note: Home Assistant and ESPHome run in `host` network mode, so they directly use ports `8123` and `6052` respectively on the host machine.*


## Roadmap
There are still a few things I want to build when I have time:
- [ ] **Server Dashboard**: A single landing page to monitor everything.
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
