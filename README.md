# SALSA

**S**ubtitle **A**nd **L**anguage **S**tream **A**utomation

A tool for managing default audio and subtitle tracks in your Plex media libraries, with batch update capabilities.

> **Inspired by [PASTA](https://github.com/cglatot/pasta)** - This project was heavily inspired by cglatot's PASTA tool. SALSA reimplements the core functionality with a backend/frontend architecture for improved reliability and Docker-native deployment.

I will surely update this later but in the mean time, have minimally servicable documentation:

## Docker Compose Quick Start

```yaml
services:
  salsa:
    image: ghcr.io/srhinos/salsa:latest
    container_name: salsa
    hostname: salsa
    ports:
      - "3000:3000"
      - "8000:8000"
      - "8001:8001"
    environment:
      - SALSA_PLEX_HOST=plex # or actual plex host
      - SALSA_PLEX_PORT=32400
      - SALSA_BACKEND_URL=http://salsa:8001
      - SALSA_API_URL=http://salsa:8000
    restart: unless-stopped
```

Then visit `http://localhost:3000`
