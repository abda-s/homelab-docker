# Homarr Dashboard

This service runs [Homarr](https://homarr.dev/), a simple, yet powerful dashboard for your server. It provides a centralized place to access all of your services.

## Prerequisites

This service requires a secret key for encrypting sensitive information.

1.  **Create the `.env` file**: Copy the `.env.example` file to a new file named `.env`.
    ```bash
    cp .env.example .env
    ```

2.  **Generate a Secret Key**: You need to generate a 64-character hex string. You can use an online generator or a command-line tool like OpenSSL:
    ```bash
    openssl rand -hex 32
    ```

3.  **Update the `.env` file**: Open the `.env` file and paste your generated key as the value for `SECRET_ENCRYPTION_KEY`.
    ```env
    SECRET_ENCRYPTION_KEY='your_64_character_hex_string_here'
    ```

## Installation

1.  Ensure you have created and configured your `.env` file in this directory.
2.  Run the stack from this directory:
    ```bash
    docker compose up -d
    ```

## Accessing the Dashboard

Once the service is running, you can access Homarr through:

*   **Directly via port**: `http://<your-host-ip>:7575`
*   **Via NGINX reverse proxy**: `http://dashboard.elwahsh.home` (requires NGINX and local DNS to be set up)
