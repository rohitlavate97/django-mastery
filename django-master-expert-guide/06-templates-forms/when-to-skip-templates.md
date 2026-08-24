# API-First Architecture vs. Django Templates: When to Skip Templates

## 1. Mental Model: Execution Architectures

### Server-Side Rendering (SSR) - Django Templates
```text
Client (Browser)                 Server (Django)                      Database
      |                                 |                                 |
      |--- 1. GET /dashboard ---------->|                                 |
      |                                 |--- 2. ORM Query --------------->|
      |                                 |<-- 3. Data ---------------------|
      |                                 |--- 4. Render template.html -----|
      |<-- 5. Return Full HTML ---------|                                 |
      |                                 |                                 |
```

### Client-Side Rendering (CSR) - SPA + API
```text
Client (Browser/React)           Server (Django DRF/Ninja)            Database
      |                                 |                                 |
      |--- 1. Initial Load (JS/HTML) -->| (CDN)                           |
      |                                 |                                 |
      |--- 2. GET /api/dashboard ------>|                                 |
      |                                 |--- 3. ORM Query --------------->|
      |                                 |<-- 4. Data ---------------------|
      |                                 |--- 5. Serialize to JSON --------|
      |<-- 6. Return JSON --------------|                                 |
      |--- 7. React renders DOM --------|                                 |
```

## 2. Why the Split Exists

For a decade, Django generated HTML. As user expectations grew (instant UI feedback, offline mode, mobile apps), architectures shifted towards Decoupled APIs (React/Vue/Mobile + Django JSON APIs). However, this heavily increases operational complexity (two codebases, two deployment pipelines, double state management). 

Modern hybrids (HTMX, Alpine) aim to bring SPA-like reactivity back to SSR.

## 3. The Options Detailed

### A. Classic Django Templates
**How it works**: Full page reloads.
**Pros**: Simplest stack, single codebase, unmatched developer velocity for CRUD.
**Cons**: Janky user experience for highly interactive apps.

### B. Django Templates + HTMX (The Modern Hybrid)
**How it works**: Django renders HTML fragments. HTMX swaps them into the DOM without full reloads.
**Pros**: SPA-like feel without writing JavaScript. Keeps state solely on the server.
**Cons**: Poor for offline apps or heavy client-side state (e.g., a complex canvas editor).

### C. Headless Django + SPA (React/Vue)
**How it works**: Django is purely a JSON API (DRF or Django Ninja). Front-end is entirely separate.
**Pros**: Reusable API for mobile apps, immense front-end ecosystem, easy to hire specialized front-end devs.
**Cons**: Massive complexity, CORS issues, token/cookie auth headaches, duplicated validation logic.

## 4. Basic Implementation: The HTMX Hybrid

Instead of returning JSON or a full page, return an HTML fragment.

```python
# views.py
from django.shortcuts import render
from .models import Task

def toggle_task(request, task_id):
    task = Task.objects.get(id=task_id)
    task.completed = not task.completed
    task.save()
    
    # Return JUST the button fragment, HTMX will swap it in
    return render(request, 'components/task_item.html', {'task': task})
```

```html
<!-- components/task_item.html -->
<li class="task {% if task.completed %}completed{% endif %}">
    {{ task.title }}
    <button 
        hx-post="{% url 'toggle_task' task.id %}"
        hx-target="closest li"
        hx-swap="outerHTML">
        Toggle
    </button>
</li>
```

## 5. Production-Ready Implementation: API-First with Django Ninja

If you need an SPA or mobile app, skip templates and use Django Ninja (fast, async, type-hinted).

```python
# api.py
from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from .models import Task

api = NinjaAPI()

class TaskSchema(Schema):
    id: int
    title: str
    completed: bool

@api.post("/tasks/{task_id}/toggle", response=TaskSchema)
def toggle_task(request, task_id: int):
    task = get_object_or_404(Task, id=task_id)
    task.completed = not task.completed
    task.save()
    return task # Ninja serializes to JSON automatically
```

## 6. Anti-Patterns 💣

### The "JSON in Templates" Frankenstein
🔴 **Anti-Pattern**: Using Django templates to inject massive JSON blobs into the window object for a React app to pick up.
```html
<script>
    window.INITIAL_STATE = {{ giant_user_context_json|safe }};
</script>
```
**Why it's bad**: 
1. Bypasses HTTP caching.
2. Huge security risk if `giant_user_context_json` contains unescaped user input (XSS).
3. Bloats the initial HTML download.

## 7. Environment-Specific Behavior

| Aspect | Template+HTMX | API + SPA |
|--------|---------------|-----------|
| **CORS** | Not an issue (same origin) | Major pain point across environments |
| **Authentication** | Session Cookies (Built-in) | JWT or HttpOnly Cookies required |
| **Caching** | Fragment caching in Redis | Edge caching (CDN) for static JS, Redis for API |
| **Deployments** | Single Heroku/Docker deploy | Two separate CI/CD pipelines |

## 8. Development Issues

🔴 **SYMPTOM**: Cross-Origin Request Blocked (CORS) in local dev.
🔍 **CAUSE**: React app running on `localhost:3000` trying to hit Django on `localhost:8000`.
🛠️ **REPRODUCE**: Make a `fetch()` call from the SPA to the API.
🔧 **DEBUG & FIX**: Install `django-cors-headers`. In local settings, set `CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]`.

## 9. Production Issues

🔴 **INCIDENT**: SPA SEO completely tanked after migration from Django Templates.
**Severity**: HIGH
**Investigation**: Googlebot crawled the React site but only saw `<div id="root"></div>` because the async API calls took too long to resolve.
**Root Cause**: Moving to a CSR (Client Side Rendered) SPA without setting up SSR (Server Side Rendering) via Next.js or Nuxt.
**Fix**: Implement Server-Side Rendering for the JS framework, or revert public pages (blog, marketing) back to Django Templates, keeping the SPA only for the logged-in dashboard.

## 10. Decision Matrix: When to Choose What

| Requirement | Django Templates | Templates + HTMX | API (DRF/Ninja) + SPA |
|-------------|------------------|------------------|-----------------------|
| Needs Mobile App API? | ❌ No | ❌ No | ✅ Yes |
| SEO Critical? | ✅ Yes | ✅ Yes | ⚠️ Hard (requires SSR in JS) |
| Offline Functionality? | ❌ No | ❌ No | ✅ Yes |
| Dev Team Size? | Solo / Small | Solo / Small | Large (Frontend + Backend teams)|
| Highly Interactive UI? (e.g. Figma clone) | ❌ No | ❌ No | ✅ Yes |
| Admin / Dashboard / CRUD? | ✅ Yes | ✅ Yes (Best choice) | ⚠️ Overkill |

## 11. Senior-Level Questions

**Q: If we use an SPA, should we use Session Auth or JWT?**
A: If the SPA and Django are on the same top-level domain (e.g., `app.domain.com` and `api.domain.com`), use Django's built-in Session Auth with `HttpOnly` cookies. It is vastly more secure than storing JWTs in `localStorage` (which is vulnerable to XSS). Only use JWTs if you have native mobile apps or 3rd-party API consumers.

**Q: Can we mix them?**
A: Yes! The most successful pattern for large monolithic startups is:
- **Marketing/SEO Pages**: Django Templates (for speed and SEO).
- **Core App/Dashboard**: React/Vue SPA mounted inside a Django template, communicating via API.
- **Admin**: Django Admin templates.

## 12. Architecture Checklist
- [ ] If building an SPA, CORS is configured securely (not `*` in production).
- [ ] If building an SPA, token/cookie strategy is defined and safe from XSS.
- [ ] If using HTMX, CSRF tokens are included in the `hx-headers` config.
- [ ] Evaluated if the interactivity actually warrants an SPA vs HTMX.
