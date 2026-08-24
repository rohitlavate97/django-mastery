# TCP, Sockets, and TLS for Django Engineers

## 1. Mental Model: The Transport Layer

```text
+-------------------+           +-----------------------+          +-----------------------+
|      Client       |   TLS     |    Load Balancer      |  TCP     |     Django Server     |
|   (Browser/App)   | ========= |  (AWS ALB / Nginx)    | -------- | (Gunicorn / Uvicorn)  |
+-------------------+ (HTTPS)   +-----------------------+ (HTTP)   +-----------------------+
          |                               |                                |
          |-- SYN ----------------------->|                                |
          |<------------------- SYN-ACK --|                                |
          |-- ACK ----------------------->|                                |
          |                               |                                |
          |-- ClientHello (TLS) --------->|                                |
          |<------------- ServerHello ----|                                |
          |-- Key Exchange -------------->|                                |
          |<--------------- Finished -----|                                |
          |                               |                                |
          |-- HTTP GET /api/ ------------>|-- SYN, SYN-ACK, ACK (Pool) --->|
          |                               |-- HTTP GET /api/ ------------->|
```

Django lives at the Application Layer (HTTP), but production performance and reliability depend entirely on the Transport Layer (TCP) and Security Layer (TLS). Understanding sockets, connection states, and TLS termination is crucial for diagnosing "502 Bad Gateway", timeouts, and connection reset errors.

## 2. Why It Exists

- **TCP**: Provides a reliable, ordered, error-checked stream of bytes between the client and server. Without it, HTTP wouldn't know if packets were dropped.
- **Sockets**: The OS-level interface for TCP. Gunicorn binds to a socket (IP:Port or Unix Domain Socket) to listen for incoming data.
- **TLS**: Encrypts the TCP stream to prevent eavesdropping and man-in-the-middle (MITM) attacks.

## 3. Internal Working: Gunicorn and Sockets

When you start Gunicorn (`gunicorn myapp.wsgi -b 0.0.0.0:8000 -w 4`), here is what happens at the OS level:

1. **Master Process**: Creates a master socket bound to `0.0.0.0:8000`.
2. **`listen()`**: The master tells the OS it is ready to accept connections (creates a backlog queue).
3. **Forking**: Master forks 4 worker processes.
4. **Inheritance**: The workers inherit the master socket file descriptor.
5. **`accept()`**: All 4 workers call `accept()` on the same socket (in Linux, this uses `epoll` or `select`). The OS load-balances incoming TCP connections among the free workers.

## 4. Connection Pooling and Keep-Alive

Establishing a TCP connection (3-way handshake) and a TLS connection (handshake) is computationally expensive and slow (due to latency). 

- **HTTP Keep-Alive**: The client and server keep the TCP connection open after a request to reuse it for subsequent requests.
- **Nginx to Gunicorn**: Nginx should use a connection pool to talk to Gunicorn, avoiding port exhaustion and latency.
- **Django to PostgreSQL**: Django opens a new TCP connection to Postgres *per request* by default. 

### Django Database Connection Pooling [DJANGO 6.1+]
Django 5.1 introduced native connection pooling, but traditionally `PgBouncer` is used.
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        'CONN_MAX_AGE': 60,  # Keep TCP connection alive for 60 seconds
        # 'CONN_HEALTH_CHECKS': True, # Required if using CONN_MAX_AGE to prevent "InterfaceError: connection already closed"
    }
}
```

## 5. TLS Termination

Encryption/Decryption is CPU-intensive. Django *should never* handle TLS directly.

- **Option A: Terminate at Load Balancer (AWS ALB)**: Client ↔(HTTPS)↔ ALB ↔(HTTP)↔ Nginx/Gunicorn. Easiest for managing AWS ACM certificates.
- **Option B: Terminate at Nginx**: Client ↔(HTTPS)↔ Nginx ↔(HTTP)↔ Gunicorn. Common in bare-metal or single-VM deployments (Let's Encrypt / Certbot).
- **End-to-End Encryption**: ALB ↔(HTTPS)↔ Nginx. Used in highly regulated environments (HIPAA/PCI) where internal network traffic must be encrypted.

## 6. Socket Exhaustion (TIME_WAIT)

When a TCP connection closes, the side that initiates the close goes into a `TIME_WAIT` state for 2 * MSL (usually 60 seconds). If your load balancer connects to Gunicorn, does a request, and closes the connection rapidly without pooling, the LB or Server will run out of ephemeral ports (~65,535).

### 💣 Anti-Pattern: Nginx without upstream keepalive
```nginx
# Bad: Closes TCP connection after every request
upstream django {
    server 127.0.0.1:8000;
}
```

### 🔧 Fix: Upstream Keepalive
```nginx
# Good: Reuses TCP connections
upstream django {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    location / {
        proxy_pass http://django;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

## 7. Environment-Specific Behavior

| Environment | Sockets & TLS |
| :--- | :--- |
| **Local** | Bound to `127.0.0.1:8000`. HTTP only. |
| **Docker Compose** | Bound to `0.0.0.0:8000`. Exposed to host. |
| **Kubernetes** | Gunicorn binds `0.0.0.0`. Ingress Controller (Nginx/Traefik) terminates TLS. |

## 8. Debugging Network Issues

- **`ss -tulpen`**: Show listening sockets and the processes owning them.
- **`netstat -an | grep TIME_WAIT | wc -l`**: Count exhausted ports.
- **`tcpdump -i eth0 port 8000`**: Sniff raw traffic going into Gunicorn.
- **`curl -vI https://api.mycorp.com`**: Debug TLS handshake, cert issuer, and HTTP headers.

## 9. Production Issues

### 🔴 INCIDENT: Intermittent 502 Bad Gateway
**Severity**: Medium
**Investigation**: 502 means Nginx couldn't communicate with Gunicorn. `ss` command showed Gunicorn listening, but dmesg showed `TCP: possible SYN flooding on port 8000. Sending cookies`.
**Root Cause**: Gunicorn's backlog (listen queue) was full. Default is 2048. Sudden burst of traffic exhausted worker capacity AND the OS backlog.
**Fix**: 
1. Increase Gunicorn workers.
2. Increase Gunicorn backlog (`-backlog 4096`).
3. Tune OS netcore somaxconn: `sysctl -w net.core.somaxconn=4096`.

### 🔴 SYMPTOM: Django `CONN_MAX_AGE` causing 500 errors
**Cause**: Load balancer scales down, or Postgres/PgBouncer terminates idle connections, but Django thinks the connection is still alive.
**Debug/Fix**: Enable connection health checks in Django settings.
```python
DATABASES['default']['CONN_HEALTH_CHECKS'] = True
```

## 10. Checklist for Production
- [ ] Gunicorn bound to localhost or private network (never public internet without reverse proxy).
- [ ] Gunicorn uses Unix Domain Sockets (`bind = 'unix:/run/gunicorn.sock'`) if Nginx is on the same machine (bypasses TCP overhead entirely).
- [ ] TLS A+ rating on SSL Labs (disable TLS 1.0/1.1, strong ciphers).
- [ ] Database connection pooling is configured (PgBouncer or `CONN_MAX_AGE`).
