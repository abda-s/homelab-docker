# Use a light Python image
FROM python:3.9-slim

# 1. Install system dependencies (FFmpeg) once during build
# We also clean up apt cache to keep the image small
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Set up the working directory
WORKDIR /app

# 3. Install Python libraries
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 4. Environment variables
# This fixes the "invisible logs" issue permanently
ENV PYTHONUNBUFFERED=1

# 5. Copy your script into the image
# (We will still volume mount it in Compose so you can edit it easily)
COPY src/ /app/src/

# 6. Default command to run the script
CMD ["python", "-m", "src.main"]
