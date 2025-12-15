# Pi-hole DNS Blocker

This service runs [Pi-hole](https://pi-hole.net/), a network-wide ad and tracker blocker that acts as a DNS sinkhole. It protects all devices on your network without requiring any client-side software.

## Installation

1.  Run the stack from this directory:
    ```bash
    docker compose up -d
    ```

## Setting Your Admin Password

On the first run, Pi-hole will generate a random password for the web interface.

1.  **Find the random password** by checking the container's logs. Run the following command shortly after starting the container:
    ```bash
    docker logs pihole 2>&1 | grep "random password"
    ```

2.  **Log in** to the admin interface using the password from the logs.

3.  **(Recommended)** **Change the password** to one of your choosing. You can do this from the command line with the following command:
    ```bash
    docker exec -it pihole pihole -a -p YOUR_NEW_PASSWORD_HERE
    ```
    Replace `YOUR_NEW_PASSWORD_HERE` with a strong, unique password.

## Accessing the Web Interface

You can access the Pi-hole admin dashboard at `http://<your-host-ip>:8085/admin`.

## Configuration

To use Pi-hole as your DNS server, you need to configure your router's DHCP settings to hand out your host machine's IP address as the DNS server for all clients.

*   **DNS Ports**: `53` (TCP/UDP)
*   **Web Interface Port**: `8085`
