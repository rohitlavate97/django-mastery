# Local Debugging Tools & Techniques

## 1. Mental Model
Local debugging involves halting execution, inspecting state, and profiling the application in a controlled environment.

## 2. Internal Working: `breakpoint()` and `pdb`
Python's built-in `breakpoint()` (PEP 553) hooks into `sys.breakpointhook()`, typically dropping you into `pdb` (Python Debugger). In Django, this pauses the worker thread, blocking the request until you type `c` (continue).

## 3. Basic Implementation: Using `breakpoint()`
```python
def my_view(request):
    data = fetch_data()
    breakpoint() # Execution pauses here
    processed = process(data)
    return JsonResponse(processed)
```

## 4. Production-Ready Implementation: `django-debug-toolbar`
```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
    INTERNAL_IPS = ['127.0.0.1']
```

## 5. Logging QuerySets
Instead of printing, use logging to trace SQL execution locally:
```python
import logging
l = logging.getLogger('django.db.backends')
l.setLevel(logging.DEBUG)
l.addHandler(logging.StreamHandler())
```

## 6. Local Development Issues
🔴 **SYMPTOM:** `runserver` hangs indefinitely.
🔍 **CAUSE:** A `breakpoint()` was hit in a background thread or signal handler where stdin is not attached.
🔧 **FIX:** Use `ipdb` with `ipdb.set_trace()` or remote debugging via VSCode.

## 7. Decision Matrix
| Tool | Use Case |
|------|----------|
| `print()` | Quick state check (not recommended) |
| `ipdb` | Deep state inspection |
| `django-debug-toolbar` | N+1 queries, template inspection |
| VSCode Debugger | Complex conditional breakpoints |

