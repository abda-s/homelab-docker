# Faster Whisper Service

This directory contains the Docker configuration for a self-hosted **Faster Whisper** service. It provides a high-performance, local API for speech-to-text transcription using the implementation by `systran/faster-whisper`.

## Overview

The service listens for audio files/streams and converts speech into text. It is designed to run locally on your server, ensuring privacy and avoiding reliance on cloud-based APIs.

## Key Features

The custom worker script (`src/`) included in this service adds significant reliability and performance improvements over a basic server setup:

### 1. Smart Polling & Queue Management
*   Continuously watches the input folder for new audio files.
*   Automatically manages file states, ignoring files that are already processed or failed.
*   Renames files upon completion (`processed_...`) or failure (`failed_...`) to keep the workspace clean.

### 2. Voice Activity Detection (VAD)
*   **Performance Boost**: Automatically detects and **removes silence** from audio files using `ffmpeg` before transcription.
*   **Efficiency**: This significantly reduces file size and transcription time, as the model doesn't waste resources processing empty noise.

### 3. Resumable Transcriptions
*   **Crash Recovery**: If the worker stops or crashes during a long job (e.g., a 2-hour podcast), it remembers exactly where it left off.
*   **Smart Resume**: On restart, it physically cuts the audio file at the last successful timestamp and only transcribes the remaining portion, seamlessly merging the results.

### 4. Robust Checkpointing & Output
*   **Real-time Saves**: Maintains a `.json` checkpoint that updates as segments are received.
*   **Rich Output**: Generates both a clean plain-text transcript and a detailed `_timestamped.txt` file with segment-by-segment timing.
*   **Atomic Writes**: Ensures files are only visible when fully written, preventing corrupted half-files.

## Future Updates

> [!NOTE]
> This service is currently in active development. There are planned updates for the future to enhance its capabilities and integration with the rest of the homelab stack, although the specific details have not yet been finalized. Stay tuned!
