# When to Skip Django Templates [DJANGO 6.1+]

## 1. Mental Model
```text
[Classic Django]
DB -> ORM -> View -> Context -> Django Template -> HTML -> Client

[Modern Django + SPA/Mobile]
DB -> ORM -> View -> Serializer (DRF/Ninja) -> JSON -> Client (React/Vue/iOS) -> HTML/UI
```

## 2. Why It Exists
Django Templates are tightly coupled to Server-Side Rendering (SSR). They struggle with highly interactive user interfaces, offline capabilities, and multi-platform clients (mobile apps).

## 3. Production-Ready Alternative (Django Ninja API)
```python
# Instead of rendering a template, return typed JSON
from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from .models import User

api = NinjaAPI()

class UserSchema(Schema):
    id: int
    username: str
    email: str

@api.get("/users/{user_id}", response=UserSchema)
def get_user(request, user_id: int):
    # This skips the template engine entirely
    return get_object_or_404(User, id=user_id)
```

## 4. Anti-Patterns
🔴 **TICKING TIME BOMB**: Injecting large JSON blobs directly into Templates for JS.
```html
<!-- BAD: XSS risk, performance hit, unescaped quotes break JS -->
<script>
    const data = {{ massive_json_dump|safe }};
</script>
```

## 5. Decision Matrix
| Architecture | Use Django Templates? |
|--------------|-----------------------|
| Content Sites / Blogs | ✅ Yes (Excellent SEO, fast initial load) |
| Admin Panels / Internal Tools | ✅ Yes (Low JS needs) |
| Highly Interactive Web Apps | ❌ No (Use React/Vue + API) |
| Mobile App Backend | ❌ No (Requires JSON/GraphQL API) |
| HTMX + Alpine.js | ✅ Yes (Modern hybrid approach) |

## 6. Senior-Level Questions
**Q: How do you handle authentication when skipping templates?**
A: With templates, Django uses Session Cookies and CSRF middleware. For APIs, you must either use JWTs, Token Authentication, or configure your SPA to send credentials (cookies) with CORS configured properly.
