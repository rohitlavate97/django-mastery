# URL Resolver Internals [DJANGO 6.1+]

## 1. Mental Model
```text
[Incoming Request Path: "/api/v1/users/42/"]
                    |
                    v
          +-------------------+
          | URLResolver Trie  |
          +-------------------+
          | - "api/"          | -> [URLResolver for API]
          |   - "v1/"         |   -> [URLResolver for V1]
          |     - "users/"    |     -> [URLPattern "users/<int:id>/"] (MATCH!)
          | - "admin/"        |
          +-------------------+
                    |
                    v
    Regex Match: `^users/(?P<id>[0-9]+)/$`
                    |
                    v
        Returns: (ViewFunc, (), {'id': 42})
```

## 2. Why It Exists
The URL resolver translates arbitrary URL paths into executable Python functions (views) efficiently, using a compiled regex trie structure to avoid linear scanning of all possible routes.

## 3. Internal Working
Trace of `django/urls/resolvers.py`:
```python
class URLResolver:
    def resolve(self, path):
        path = str(path)  # Cast to string
        tried = []
        match = self.pattern.match(path)
        if match:
            new_path, args, kwargs = match
            for pattern in self.url_patterns: # Iterates over patterns
                try:
                    sub_match = pattern.resolve(new_path)
                except Resolver404 as e:
                    tried.extend([(pattern.pattern.regex.pattern + '   ' + t) for t in e.args[0].get('tried', [])])
                else:
                    if sub_match:
                        # Combine args and kwargs from current and sub-match
                        return ResolverMatch(
                            sub_match.func,
                            args + sub_match.args,
                            {**kwargs, **sub_match.kwargs},
                            sub_match.url_name,
                            [self.app_name] + sub_match.app_names,
                            [self.namespace] + sub_match.namespaces,
                            self._route,
                        )
            raise Resolver404({'tried': tried, 'path': new_path})
        raise Resolver404({'path': path})
```

## 4. Basic Implementation
```python
from django.urls import path
from . import views

urlpatterns = [
    path('articles/<int:year>/', views.year_archive, name='year-archive'),
]
```

## 5. Production-Ready Implementation
```python
from django.urls import path, include, register_converter
from . import views, converters

# Register custom path converter for performance/safety
register_converter(converters.FourDigitYearConverter, 'yyyy')

app_name = 'articles'
urlpatterns = [
    # Include namespaces to prevent collision
    path('api/v1/', include([
        path('<yyyy:year>/', views.ArticleYearView.as_view(), name='archive'),
        path('<yyyy:year>/<slug:slug>/', views.ArticleDetailView.as_view(), name='detail'),
    ])),
]
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Catch-all regex placed too early.
```python
urlpatterns = [
    re_path(r'^.*$', views.catch_all), # BROKEN: Shadows all routes below it
    path('admin/', admin.site.urls),    # Unreachable!
]
```

## 7. Environment-Specific Behavior
| Environment | APPEND_SLASH | Behavior |
|-------------|--------------|----------|
| Local Dev | True | Auto-redirects `/api/users` to `/api/users/` (301). |
| Docker | True | Same, but 301s add latency. |
| 100k RPS Prod | False | Rely on strict routing (API clients must send exact paths) to save 1 full round trip. |

## 8. Local Development Issues
🔴 SYMPTOM: `Reverse for 'article-detail' not found.`
🔍 CAUSE: Using `reverse('article-detail')` when the app has a namespace (`app_name = 'articles'`).
🔧 FIX: Use `reverse('articles:article-detail')`.

## 9. Production Issues
INCIDENT: ReDoS (Regular Expression Denial of Service).
SEVERITY: Critical
CAUSE: Inefficient regex `r'^user/([a-z]+)*$'` took O(2^n) time to process long invalid paths.
FIX: Use `path('user/<str:username>/')` instead of complex `re_path`, or use strict bounded regex `r'^user/([a-z]{1,50})$'`.

## 10. Failure Simulation
```python
import pytest
from django.urls import resolve, Resolver404

def test_invalid_url_raises_404():
    with pytest.raises(Resolver404):
        resolve("/nonexistent/path/")
```

## 11. Decision Matrix
| Feature | `path()` | `re_path()` |
|---------|----------|-------------|
| Readability | Excellent | Poor |
| Type Casting | Yes (Converters) | No (Strings only) |
| Complex logic | Limited | Full Regex Power |

## 12. Senior-Level Questions
**Q: When is the URLconf loaded and compiled into regex?**
A: It is evaluated lazily on the first request, then cached in memory. In multi-process deployments with `--preload`, it's compiled once in the master process.

## 13. Production Checklist
- [ ] No unbounded regex in `re_path`.
- [ ] `APPEND_SLASH` is considered for APIs.
- [ ] Namespaces used for all apps.
