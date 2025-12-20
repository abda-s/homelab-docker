# NGINX Reverse Proxy

This service runs NGINX as a reverse proxy, providing a single entry point for all the services in this homelab setup. It simplifies access by using subdomains for each service instead of remembering IP addresses and port numbers.

## Features

*   **Centralized Access**: Access all your services through a single IP address using unique subdomains.
*   **Simplified URLs**: Use subdomains like `pihole.elwahsh.home` instead of `192.168.1.111:8085`.

## Configuration

The NGINX configuration is located in the `conf.d/services.conf` file. This file contains the server blocks that define how NGINX routes traffic to your other Docker containers based on the requested subdomain.

### `services.conf`

This configuration is set up to proxy requests to services running on the host at IP address `192.168.1.111`.

**Example Configuration for Pi-hole:**
```nginx
server {
    listen 80;
    server_name pihole.elwahsh.home;

    location / {
        proxy_pass http://192.168.1.111:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Local DNS Setup

To use these subdomains, you must have a local DNS server (like the Pi-hole in this project) configured to resolve all `*.elwahsh.home` domains to the IP address of the machine running this NGINX container.

## Installation

1.  Ensure that the IP address `192.168.1.111` in `conf.d/services.conf` matches the IP address of your Docker host.
2.  Run the stack from this directory:
    ```bash
    docker compose up -d
    ```

## Usage

Once NGINX is running and your local DNS is configured, you can access your services using the subdomains configured in `services.conf` (e.g., `http://pihole.elwahsh.home`).