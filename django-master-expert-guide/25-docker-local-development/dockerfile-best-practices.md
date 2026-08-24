# Dockerfile Best Practices for Django

## 1. Mental Model
```text
[Source Code] -> (Build Stage: Compile dependencies) -> (Final Stage: Copy built artifacts, set permissions) -> [Optimized Container Image]
```
A Dockerfile is not just a setup script; it is a blueprint for immutable infrastructure. Every `RUN`, `COPY`, and `ADD` command creates a new layer. Your goal is to maximize cache hits, minimize image size, and eliminate security vulnerabilities.

## 2. Why It Exists
Running Django directly on virtual machines leads to the "it works on my machine" problem. Docker packages the OS, dependencies, and code into a single artifact. However, naive Dockerfiles result in gigabyte-sized, slow-building, insecure images.

## 3. Internal Working
Docker uses a union file system (like OverlayFS). When building, Docker caches each layer. If a layer changes (e.g., `COPY . .` changes because a source file was edited), that layer and ALL subsequent layers are invalidated and rebuilt.

## 4. Basic Implementation
```dockerfile
# 🔴 ANTI-PATTERN: The Naive Dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```
*Why it's bad:* Runs as root, invalidates dependency cache on every code change, includes build tools in final image, uses `runserver` in production.

## 5. Production-Ready Implementation
```dockerfile
# ✅ PRODUCTION-READY: Multi-stage, non-root, cached
# Stage 1: Builder
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install OS build dependencies (e.g., for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to cache them
COPY requirements/prod.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r prod.txt

# Stage 2: Final
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1

# Create a non-root user
RUN addgroup --system django \
    && adduser --system --ingroup django django

WORKDIR /app

# Install runtime dependencies (e.g., libpq5)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies from wheels
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY --chown=django:django . .

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "core.wsgi:application"]
```

## 6. Anti-Patterns
🔴 **Running as Root:** Never use the default root user. An RCE vulnerability in Django would give attackers root access to the container.
🔴 **Copying Code before Dependencies:** `COPY . .` followed by `RUN pip install`. This invalidates the pip install cache every time you change a Python file.
🔴 **Leaking Secrets:** Passing secrets as `ENV` variables during build time or using `COPY .env`.

## 7. Environment-Specific Behavior
| Environment | Behavior | Consideration |
|-------------|----------|---------------|
| Local | Uses `docker-compose` | Might override `CMD` to use `runserver` and mount volumes. |
| CI | Builds image | Needs fast caching. Use Docker Buildx with `--cache-from`. |
| Production | Runs image | Image must be immutable. No volume mounts for code. |

## 8. Local Development Issues
🔴 **SYMPTOM:** Docker build takes 5 minutes every time you change a view.
🔍 **CAUSE:** The `COPY . .` command is placed before the `pip install` command.
🔧 **FIX:** Move `COPY requirements.txt .` and `RUN pip install` above `COPY . .`.

## 9. Production Issues
🔴 **INCIDENT:** Security scan failed, deployment blocked.
* **Severity:** High
* **Investigation:** Trivy scanner found critical vulnerabilities in `curl` and `openssl`.
* **Root Cause:** Using the `python:3.12` image (which is based on a full Debian distribution) instead of the `slim` variant.
* **Fix:** Switched to `python:3.12-slim-bookworm` and added `apt-get update && apt-get upgrade -y` in the builder.

## 10. Failure Simulation
Run `docker exec -it <container> bash` on your production image and try to run `apt-get install nmap`. If it succeeds, your container is running as root (or you didn't drop privileges properly).

## 11. Decision Matrix
| Base Image | Pros | Cons |
|------------|------|------|
| `python:3.12` | Everything works out of the box | Massive size (~1GB), large attack surface |
| `python:3.12-slim` | Small, secure | Requires manual apt-get for C extensions |
| `python:3.12-alpine`| Tiny size | Musl libc causes issues with Python wheels, slow builds |

## 12. Senior-Level Questions
**Q: Why use `pip wheel` in a builder stage instead of just `pip install` and copying the virtualenv?**
A: Virtualenvs encode absolute paths. Copying a virtualenv from one stage to another can cause subtle breakages if the paths don't match perfectly. Building wheels compiles C extensions once, and then you cleanly install those pre-compiled wheels in the final stage's global python environment, ensuring a clean, reproducible state.

## 13. Production Checklist
- [ ] Multi-stage build used.
- [ ] `USER django` (non-root) is set.
- [ ] `python-slim` base image utilized.
- [ ] Dependency installation cached (COPY requirements first).
- [ ] `.dockerignore` configured (ignoring `.git`, `__pycache__`, `.env`).
- [ ] Scanned with Trivy or Snyk.
