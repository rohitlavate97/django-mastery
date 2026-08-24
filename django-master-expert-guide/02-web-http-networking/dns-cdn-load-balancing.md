# DNS, CDN, and Load Balancing for Django

## 1. Mental Model: The Edge and Routing

```text
+----------+      1. DNS Lookup      +-------------+
|  Client  | ----------------------> | Route 53 /  |
|          | <---------------------- | Cloudflare  |
+----------+      IP: 192.0.2.1      +-------------+
     |
     | 2. HTTP GET /static/app.js
     v
+----------+      3. Cache Hit       +-------------+
|   CDN    | <---------------------> | Edge Cache  |
+----------+                         +-------------+
     | 4. HTTP GET /api/users/ (Cache Miss / Dynamic)
     v
+----------+      5. Route Traffic   +-------------+
| Load Bal | ----------------------> | Target Grp  |
| (ALB/NLB)|                         +-------------+
+----------+                            |      |
     |        +-------------------------+      |
     v        v                                v
+------------------+                    +------------------+
| Nginx + Gunicorn |                    | Nginx + Gunicorn |
| (Django App A)   |                    | (Django App B)   |
+------------------+                    +------------------+
```

Before a request ever hits your Django application, it travels through a gauntlet of global infrastructure. Misconfigurations here cause downtime that no amount of Django code optimization can fix.

## 2. Why It Exists

- **DNS**: Translates human-readable domains (`api.example.com`) to IP addresses. It allows routing traffic dynamically without users changing URLs.
- **CDN (Content Delivery Network)**: Caches static assets (`.css`, `.js`, images) physically close to the user to reduce latency and save origin server bandwidth.
- **Load Balancer**: Distributes incoming traffic across multiple Django instances to ensure high availability (HA) and horizontal scaling.

## 3. Internal Working: DNS Resolution

1. Browser checks local cache.
2. OS checks `/etc/hosts`.
3. OS queries configured resolver (e.g., 8.8.8.8).
4. Resolver queries Root DNS -> TLD (.com) -> Authoritative Nameserver (Route 53).
5. Authoritative server returns A Record (IPv4) or AAAA Record (IPv6).

**TTL (Time To Live)** dictates how long downstream resolvers cache the IP. If you need to migrate servers, lower the TTL to 60 seconds 24 hours in advance.

## 4. CDNs and Django Integration

Django is designed to generate dynamic content, not serve static files efficiently. CDNs like Cloudfront or Cloudflare handle this.

### Basic Implementation (Django `collectstatic`)
Django's `StaticFilesStorage` collects files to a directory. In production, you upload these to an S3 bucket and point a CDN at the bucket.

### Production-Ready Implementation (django-storages)
```python
# settings.py
INSTALLED_APPS += ['storages']

# S3 Configuration
AWS_STORAGE_BUCKET_NAME = 'my-django-assets'
AWS_S3_CUSTOM_DOMAIN = 'cdn.mycorp.com' # Points to CloudFront

# Django routing for static/media
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

### Cache Invalidation
When you deploy new CSS, you don't want users seeing old cached CSS.
- **Django Fix**: Use `ManifestStaticFilesStorage`. It appends an MD5 hash to filenames (`style.a1b2c3d4.css`). 
- **CDN Fix**: You never need to invalidate the CDN cache because the URL changes entirely on every deployment!

## 5. Load Balancers

- **Layer 4 (Transport, NLB)**: Forwards raw TCP packets. Extremely fast. Cannot read HTTP headers.
- **Layer 7 (Application, ALB)**: Terminates TLS, reads HTTP headers (Host, Cookies). Can route based on URL path (`/api/` goes to Django, `/blog/` goes to WordPress).

### Connection Draining
When you deploy, the ALB needs to stop sending new requests to the old Django container, but wait for active requests to finish. This is called connection draining (deregistration delay). Set this to ~30-60s depending on your longest Django view timeout.

## 6. Django Configuration for Proxies

If your Django app is behind an ALB, the socket connection comes from the ALB's private IP, not the client's IP. Furthermore, the ALB communicates with Django over HTTP, not HTTPS.

### 💣 Anti-Pattern: Ignoring X-Forwarded Headers
```python
# View
client_ip = request.META.get('REMOTE_ADDR') # Will return ALB internal IP (e.g., 10.0.1.55)!
is_secure = request.is_secure() # Will return False, breaking CSRF and absolute URL generation!
```

### 🔧 Fix: Tell Django it is behind a trusted proxy
```python
# settings.py
# Trust the ALB to tell us if the original request was HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Use the Host header provided by the client, not the ALB's internal IP
USE_X_FORWARDED_HOST = True

ALLOWED_HOSTS = ['api.mycorp.com', '10.0.0.0/16'] # Allow actual domain and VPC CIDR for health checks
```

## 7. Production Issues

### 🔴 INCIDENT: Load Balancer Health Check Failures Loop
**Severity**: High (Service Outage)
**Investigation**: ALB marks Django instances as "Unhealthy" and terminates them. Auto-scaling group spins up new instances, which also become Unhealthy.
**Root Cause**: The ALB health check was pointing to `/api/health/`. The ALB accesses it via the instance's IP address (e.g., `http://10.0.1.50/api/health/`). Because `10.0.1.50` was NOT in Django's `ALLOWED_HOSTS`, Django returned `400 Bad Request`. ALB expects `200 OK`.
**Fix**: 
Write a custom middleware or modify `ALLOWED_HOSTS` to accept the VPC CIDR block, or use a health check endpoint that bypasses the host check.

### 🔴 SYMPTOM: CSRF Verification Failed on HTTPS site
**Cause**: The site is HTTPS, but Django thinks it is HTTP because TLS is terminated at the ALB. Django sees the `Referer` header as `https://...` but thinks it is hosted on `http://...`. The strict CSRF referer checking fails.
**Fix**: Ensure `SECURE_PROXY_SSL_HEADER` is set correctly, and `CSRF_TRUSTED_ORIGINS = ['https://api.mycorp.com']`.

## 8. Checklist for Production
- [ ] CDN is configured for `/static/` and `/media/`.
- [ ] Django uses Manifest storage to prevent CSS/JS caching bugs.
- [ ] Health check endpoint `/healthz` exists, accesses DB lightly to verify connectivity, and returns 200.
- [ ] `ALLOWED_HOSTS` includes LB domain, production domain, and VPC IPs.
- [ ] WAF (Web Application Firewall) attached to ALB/Cloudflare to block basic SQLi/XSS before it hits Django.
