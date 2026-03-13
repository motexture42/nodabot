# Skill: Docker Expert

## Overview
Use this skill when asked to containerize an application, write a `Dockerfile`, or create a `docker-compose.yml` setup.

## Best Practices for Dockerfiles
1. **Base Images**: Prefer slim or alpine versions of base images (e.g., `python:3.11-slim`, `node:20-alpine`) to reduce attack surface and image size.
2. **Layer Caching**: Copy dependency files (like `package.json` or `requirements.txt`) and install dependencies *before* copying the rest of the source code. This optimizes the build cache.
3. **Non-Root User**: Never run the application as root if possible. Create a dedicated user and switch to it using the `USER` directive.
4. **Environment Variables**: Define necessary environment variables using `ENV`, but do not hardcode secrets.

## Docker Compose
- Always specify a `version` (e.g., `'3.8'`).
- Use named volumes for database persistence.
- Define explicit ports (e.g., `"8080:80"`).

## Common Errors
- `exec format error`: Usually means a script is missing a shebang or doesn't have execute permissions (`chmod +x`).
- `port already allocated`: Ensure you map to an available host port.