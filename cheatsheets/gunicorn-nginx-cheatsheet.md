# Gunicorn & Nginx Production Cheat Sheet

## 1. Gunicorn Worker Formulas

```python
# gunicorn.conf.py
import multiprocessing

# Workers for I/O bound Django workloads: (2 x CPU Cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Threaded worker model (recommended for I/O bound DB & API traffic)
worker_class = "gthread"
threads = 4  # 4 threads per worker

# Timeouts
timeout = 30           # Kill silent workers after 30s
graceful_timeout = 30  # Allow 30s for inflight requests on SIGTERM

# Memory leak prevention (Worker Recycling)
max_requests = 1000
max_requests_jitter = 100  # Avoid all workers restarting at once

# Keep-alive matching Nginx upstream
keepalive = 5
```

---

## 2. Nginx Reverse Proxy Upstream Configuration

```nginx
# /etc/nginx/conf.d/django.conf
upstream django_app {
    server 127.0.0.1:8000;
    keepalive 32;  # Maintain 32 idle keepalive connections to Gunicorn
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Rate Limiting
    limit_req zone=api_limit burst=20 nodelay;

    location /static/ {
        alias /app/staticfiles/;
        expires 365d;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location / {
        proxy_pass http://django_app;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
        
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
    }
}
```
