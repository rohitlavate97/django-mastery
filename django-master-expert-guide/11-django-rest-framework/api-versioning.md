# API Versioning Strategies

## 1. Mental Model

APIs are contracts. When the data structure or logic fundamentally changes, the contract breaks. Versioning allows serving both old and new contracts simultaneously.

```text
Request (v1 vs v2)
  |-- URL: /api/v1/users/
  |-- Header: Accept: application/json; version=1.0
  |-- Query: /api/users/?version=1
  v
DRF Versioning Class determines `request.version`
  v
View / Serializer execution branches based on `request.version`
```

## 2. Supported Versioning Schemes

1. **URLPathVersioning** (`/v1/`): Explicit, easily cacheable by CDNs, easily explored in browser. **(Industry Standard & Recommended)**
2. **AcceptHeaderVersioning**: REST purist approach, clean URLs, hard to test in browser without tools.
3. **NamespaceVersioning**: Uses Django URL namespaces (`v1:users-list`). Great for completely separate Django apps per version.
4. **QueryParameterVersioning**: Good for quick scripts, not ideal for production routing.

## 3. Production Implementation: URLPathVersioning

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'VERSION_PARAM': 'version'
}

# urls.py
urlpatterns = [
    re_path(r'^api/(?P<version>(v1|v2))/users/$', users_list),
]
```

## 4. Branching Logic (Views vs Serializers)

### Branching in Views
```python
class UserViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.version == 'v2':
            return UserSerializerV2
        return UserSerializerV1
```

### Namespace Versioning Pattern (The Cleanest Separation)
Instead of littering `if version == 'v2'` everywhere, duplicate the app routing and logic.

```python
# urls.py
urlpatterns = [
    path('api/v1/', include('myapi.urls_v1', namespace='v1')),
    path('api/v2/', include('myapi.urls_v2', namespace='v2')),
]
```

## 5. Deprecation Strategy

1. Announce `v3` release.
2. Mark `v1` as deprecated via response headers: `Warning: 299 - "API v1 is deprecated and will be removed on 2025-01-01"`.
3. Monitor `v1` traffic logs to identify lagging clients.
4. Hard cut-off on sunset date (Return 410 Gone).

## 6. Production Checklist
- [ ] Versioning strategy is established BEFORE initial production launch.
- [ ] CDN caching rules account for version paths/headers.
- [ ] Sunset policy is documented for API consumers.
