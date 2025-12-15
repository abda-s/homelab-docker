# Smarthome Stack

This stack runs services related to home automation.

## Services

### Home Assistant

This service runs [Home Assistant](https://www.home-assistant.io/), a powerful open-source home automation platform. It allows you to track and control all your smart devices from a central hub and build powerful automations.

*   **Web Interface**: `http://<your-host-ip>:8123`
*   **Configuration Path**: `./homeassistant`
*   **Network Mode**: `host`
*   **Privileged Mode**: `true`

### ESPHome

[ESPHome](https://esphome.io/) is a system to control your ESP8266/ESP32 boards by simple yet powerful configuration files and have them remotely controlled through Home Automation systems.

*   **Web Interface**: `http://<your-host-ip>:6052`
*   **Configuration Path**: `./esphome`
*   **Network Mode**: `host`
*   **Privileged Mode**: `true`

## Installation

1.  Navigate to this directory.
2.  (Optional) Set ESPHome credentials by creating a `.env` file:
    ```env
    ESPHOME_USERNAME=admin
    ESPHOME_PASSWORD=your-secret-password
    ```
3.  Run the stack:
    ```bash
    docker compose up -d
    ```

## Configuration Details

Both services in this stack run in `network_mode: host` and with `privileged: true`.

*   **Host Network Mode (`network_mode: host`)**: This gives the containers full access to the host's network, which is often required for discovering smart devices.
*   **Privileged Mode (`privileged: true`)**: This can be necessary for giving the containers access to hardware devices like Zigbee/Z-Wave USB controllers or for flashing ESP boards.

> **Security Warning**: Using `network_mode: host` and `privileged: true` grants containers significant access to your host machine. This is a common configuration for Home Assistant and ESPHome to ensure full functionality, but be aware of the security implications.
