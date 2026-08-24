# Python Packaging & Dependencies for Django Projects

## 1. Mental Model
```text
+-------------------------------------------------------+
|   Django Project App                                  |
+-------------------------------------------------------+
|   Dependency Manager (Poetry / pip-tools / uv)        |
|   Resolves graph, outputs locked versions + hashes    |
+-------------------------------------------------------+
|   Virtual Environment (venv)                          |
|   Isolates interpreter and site-packages              |
+-------------------------------------------------------+
```

## 2. Why It Exists
Django projects depend on dozens of external packages (psycopg2, celery, djangorestframework). Without strict packaging controls:
- **Works on my machine**: Versions diverge between devs.
- **Supply chain attacks**: A compromised package is auto-downloaded on CI.
- **Dependency hell**: Upgrading package A breaks package B.

## 3. Dependency Management Ecosystem
### pip + requirements.txt
- **Pros**: Built-in, universal.
- **Cons**: No native dependency resolution (until recently). `pip freeze` includes transitive dependencies without tracking why they are there.

### pip-tools
- **Pros**: Clean, simple. Compiles `requirements.in` to a hashed, pinned `requirements.txt`.
- **Cons**: Still relies on standard pip for installation.

### Poetry
- **Pros**: Powerful dependency resolver, creates `poetry.lock`, handles virtualenvs.
- **Cons**: Slow resolution, strictly adheres to PEP 517.

### uv (Modern Alternative)
- **Pros**: Written in Rust. Blazing fast drop-in replacement for pip/pip-tools/virtualenv.

## 4. Reproducible Builds and Security
**🔴 Anti-Pattern (Ticking Time Bomb)**: `pip install -r requirements.txt` without versions or hashes.
```text
# requirements.txt
django
djangorestframework
requests
```
*Symptom*: Production deployment breaks randomly on Tuesday because `requests` released a new major version.

**✅ Production-Ready Implementation (Lock Files with Hashes)**:
Always use a lockfile (e.g. via `pip-compile --generate-hashes`).
```text
# requirements.txt (compiled)
django==4.2.1 \
    --hash=sha256:abcd...
djangorestframework==3.14.0 \
    --hash=sha256:1234...
```

## 5. Docker + Dependencies (Layer Caching)
When containerizing Django, order matters to maximize Docker layer caching.

```dockerfile
# ✅ GOOD PATTERN
FROM python:3.12-slim

WORKDIR /app

# 1. Install system dependencies first
RUN apt-get update && apt-get install -y libpq-dev gcc

# 2. Copy ONLY dependency files
COPY requirements.txt .

# 3. Install dependencies (This layer caches if requirements.txt hasn't changed!)
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of the application code
COPY . .

CMD ["gunicorn", "myapp.wsgi"]
```

## 6. Local Development Issues
🔴 **SYMPTOM**: `ModuleNotFoundError` for a package that is definitely installed.
🔍 **CAUSE**: The IDE (VSCode/PyCharm) or terminal is using the global Python interpreter instead of the virtualenv.
🔧 **FIX**: Always activate the virtualenv (`source venv/bin/activate`) or set the correct interpreter path in the IDE `.vscode/settings.json`.

## 7. Security Scanning
Always scan dependencies in CI.
- **pip-audit**: Scans Python environments for known vulnerabilities (CVEs).
- **Dependabot / Renovate**: Auto-creates PRs to update outdated packages safely.

## 8. Production Checklist
- [ ] Dependencies are explicitly pinned (`==`).
- [ ] Hashes are verified during installation (`--require-hashes`).
- [ ] Dockerfile optimizes layer caching for `requirements.txt` or `poetry.lock`.
- [ ] CI/CD pipeline runs `pip-audit` or equivalent vulnerability scanning.
- [ ] Internal packages (if any) are pulled from a secure private PyPI server.
