# YTPTube Service

This directory contains the Docker configuration for **YTPTube**, a self-hosted YouTube downloader that provides a web interface for downloading videos and audio.

## Overview

YTPTube allows you to easily download content from YouTube and other supported sites directly to your server. It features a simple web UI and manages downloads in the `downloads/` directory.

## Access

Once the stack is running, you can access the service at:
- **URL**: `http://ytp.elwahsh.home`
- **Port**: `3333` (Internal)

## Configuration

The service is configured via `docker-compose.yml` and the `config/` directory. By default, authentication is disabled in the compose file, but can be enabled by uncommenting the environment variables.
