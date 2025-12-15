# Home Assistant

This service runs [Home Assistant](https://www.home-assistant.io/), a powerful open-source home automation platform. It allows you to track and control all your smart devices from a central hub and build powerful automations.

## Installation

1.  Navigate to this directory.
2.  Run the stack:
    ```bash
    docker compose up -d
    ```

## Accessing the Web Interface

Once started, Home Assistant will be accessible on your local network at `http://<your-host-ip>:8123`.

The first time you start it, you will be guided through an onboarding process to create an admin user and set up your home.

## Configuration Details

*   **Configuration Path**: The main Home Assistant configuration is stored in the `homeassistant` subdirectory within this folder. Any changes you make through the UI will be saved here.
*   **Network Mode**: This container runs in `network_mode: host`. This gives it full access to the host's network, which is often required for discovering smart devices on your network.
*   **Privileged Mode**: This container runs with `privileged: true`. This can be necessary for giving Home Assistant access to hardware devices like Zigbee or Z-Wave USB controllers.

> **Security Warning**: Using `network_mode: host` and `privileged: true` grants the container significant access to your host machine. This is a common configuration for Home Assistant to ensure full functionality, but be aware of the security implications. Only use these settings if they are required for your specific setup.
