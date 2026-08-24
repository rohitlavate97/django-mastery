# Docker Debugging in Local Development

## 1. Mental Model
```text
[Host Machine (VS Code/PyCharm)] 
       | (Network Port Mapping)
       | (Volume Mounts)
       v
[Docker Container namespace]
   -> Filesystem: overlayFS
   -> Network: docker0 bridge
   -> Process: PID 1 (gunicorn / python)
```
Debugging inside a container requires bridging the gap between your host OS and the isolated container environment. The container has its own file permissions, network stack, and process tree.

## 2. Why It Exists
"It works on my machine" often translates to "it doesn't work in the container." You need standard techniques to inspect a running container, step through code, analyze network traffic, and read memory limits.

## 3. Internal Working
When a container exits with code 137, it means the Linux OOM (Out of Memory) Killer terminated it (Exit Code = 128 + 9 (SIGKILL) = 137). 
When you attach a debugger (like `debugpy`), it opens a TCP socket inside the container that your host IDE connects to via port forwarding.

## 4. Basic Implementation
```bash
# 🔴 ANTI-PATTERN: Restarting the container repeatedly with print() statements
docker-compose restart web
# (Wait 10 seconds for boot...)
# "Ah, it didn't print. Let me add another print and restart."
```

## 5. Production-Ready Implementation
**Step 1: Attaching a Debugger (debugpy for VS Code)**

In `docker-compose.yml`:
```yaml
services:
  web:
    build: .
    command: python -m debugpy --listen 0.0.0.0:5678 -m django runserver 0.0.0.0:8000
    ports:
      - "8000:8000"
      - "5678:5678" # Debug port
    volumes:
      - .:/app
```

In `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Remote Attach",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "/app"
                }
            ]
        }
    ]
}
```
Set a breakpoint in VS Code, attach the debugger, and send a request!

**Step 2: Inspecting Container State**
```bash
# Get a shell inside the running container
docker exec -it <container_name> /bin/bash

# Check internal DNS resolution
docker exec -it <container_name> ping db

# Check container logs (follow)
docker logs -f <container_name>

# Inspect memory/CPU usage
docker stats
```

## 6. Anti-Patterns
🔴 **Installing editors inside the container:** Running `apt-get install vim` inside the container to edit files directly. Use volume mounts and edit on your host.
🔴 **Ignoring Exit Codes:** Assuming a container crash is a random bug. Exit codes have specific meanings (1 = App Error, 137 = OOM, 139 = Segfault).

## 7. Environment-Specific Behavior
| Environment | Debugging Strategy | Consideration |
|-------------|--------------------|---------------|
| Local | `debugpy` / VS Code attach | Full breakpoint capability |
| Staging | Sentry, Datadog | Never attach debuggers to remote environments |
| CI | `docker-compose logs` | Rely on automated test output |

## 8. Local Development Issues
🔴 **SYMPTOM:** Container exits immediately with code 0 or 1.
🔍 **CAUSE:** The entrypoint script or main command failed, or it executed a script that didn't block (like running a daemon in the background).
🔧 **FIX:** Change the command in `docker-compose.yml` to `command: tail -f /dev/null` to keep the container alive, then `docker exec -it` inside to manually run the startup script and observe the error.

## 9. Production Issues
🔴 **INCIDENT:** Django container randomly restarts in production.
* **Severity:** High
* **Investigation:** `docker ps` showed the container "Up 2 minutes", meaning it restarted. Checking `docker inspect <container_id>` revealed `"OOMKilled": true`.
* **Root Cause:** A specific view was loading a massive QuerySet into memory, exceeding the container's 512MB RAM limit.
* **Fix:** Used `.iterator()` on the QuerySet and increased the container memory limit to 1GB.

## 10. Failure Simulation
To simulate an OOM Kill (Exit 137), set a memory limit in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 50M
```
Then write a Django view that does `x = "a" * 100_000_000` and hit the endpoint. Watch the container instantly die.

## 11. Decision Matrix
| Tool | Best For | Complexity |
|------|----------|------------|
| `print()` + logs | Quick variable inspection | Low |
| `debugpy` / IDE | Complex logical bugs, tracing | Medium (requires setup) |
| `pdb` | Terminal junkies | Low |
| `strace` | Low-level C extension/kernel bugs | High |

## 12. Senior-Level Questions
**Q: How do you fix "Permission denied" errors for files created by the container in a volume mount?**
A: When a container runs as root, files it creates in the bind-mounted directory are owned by root on the host machine. To fix this, ensure the container runs as your host user's UID/GID. You can pass these as build args or environment variables and configure the container user to match your host user.

## 13. Production Checklist
- [ ] Debugger ports (5678) are NEVER exposed in production YAMLs.
- [ ] Exit codes are monitored by an orchestration tool (K8s/ECS).
- [ ] Resource limits (Memory/CPU) are explicitly defined to prevent a single container from starving the host.
- [ ] Volume mounts are strictly used for development, never for production code injection.
