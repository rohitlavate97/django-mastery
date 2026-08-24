# Function-Based Views (FBV) vs Class-Based Views (CBV) [DJANGO 6.1+]

## 1. Mental Model
```text
[URL Match]
    |
    v
FBV:   my_view(request, **kwargs)  -->  [Business Logic]  --> Response
    
CBV:   MyView.as_view()(request, **kwargs)
          |->  view() wrapper
                 |-> self.dispatch()
                        |-> getattr(self, request.method.lower())()
                               |-> get() / post() / put() --> Response
```

## 2. Why It Exists
**FBVs** are simple and explicit. 
**CBVs** provide code reuse through inheritance and mixins (e.g., `LoginRequiredMixin`), avoiding boilerplate for standard CRUD operations.

## 3. Internal Working
Trace of `django/views/generic/base.py`:
```python
class View:
    @classmethod
    def as_view(cls, **initkwargs):
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)
            self.setup(request, *args, **kwargs)
            return self.dispatch(request, *args, **kwargs)
        return view

    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() in self.http_method_names:
            handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed
        return handler(request, *args, **kwargs)
```

## 4. Production-Ready Implementation
```python
# Modern approach often favors explicit FBVs for APIs, or strict CBVs for standard HTML.
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .models import Article

# CBV approach (Extremely concise for standard patterns)
class ArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = 'articles/list.html'
    paginate_by = 20
    
    def get_queryset(self):
        # Custom logic added easily
        return super().get_queryset().filter(author=self.request.user).select_related('author')
```

## 5. Anti-Patterns
🔴 **TICKING TIME BOMB**: Mutating `self` in CBVs during requests.
```python
class BadView(View):
    def get(self, request):
        self.counter += 1 # BAD: self is instantiated per-request, but if you mutate class attributes, it leaks across threads!
        return HttpResponse("OK")
```

## 6. Decision Matrix
| Feature | FBV | CBV |
|---------|-----|-----|
| Simplicity & Readability | 🟢 High | 🔴 Low (due to deep inheritance) |
| Standard CRUD Code Reuse | 🔴 Low | 🟢 High |
| Decorator Support | 🟢 Native | 🟡 Requires `@method_decorator` |
