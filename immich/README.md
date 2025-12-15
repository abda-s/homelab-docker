# Immich - Self-Hosted Photo and Video Backup

This service runs [Immich](https://immich.app/), a high-performance, self-hosted photo and video backup solution. It provides a private and secure alternative to services like Google Photos or iCloud Photos.

## Prerequisites

Immich requires an `.env` file for its core configuration, including database credentials and the location for your uploaded media.

1.  **Get the necessary files**: The Immich project updates frequently. It is highly recommended to get the latest `docker-compose.yml` and a template `.env` file directly from the official releases page:
    *   [**Immich Releases Page**](https://github.com/immich-app/immich/releases/latest)

2.  **Create the `.env` file**: Download the `example.env` from the release, rename it to `.env`, and place it in this directory.

3.  **Customize the `.env` file**: Open the `.env` file and, at a minimum, you must set the `UPLOAD_LOCATION` to a path on your host machine where you want your photos and videos to be stored. You can also customize other variables as needed.

    Example `.env` customization:
    ```env
    # The location where your files are stored.
    UPLOAD_LOCATION=C:/Users/YourUser/Pictures/immich_library

    # You can also change the database location if desired
    # DB_DATA_LOCATION=C:/Users/YourUser/Documents/immich_db
    ```

## Installation

1.  Ensure you have customized your `.env` file in this directory.
2.  Run the stack from this directory:
    ```bash
    docker compose up -d
    ```

## Accessing the Web Interface

Once all the services have started, you can access the Immich web interface at `http://<your-host-ip>:2283`.

You will be prompted to create an admin account on your first visit.

> **Note**: This stack consists of multiple containers, including the main server, a machine-learning service, a database, and a Redis cache. It may take a few minutes for all services to initialize the first time you run them.
