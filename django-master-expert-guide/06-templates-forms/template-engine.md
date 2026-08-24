# Django Template Engine Internals [DJANGO 6.1+]

## 1. Mental Model
```text
[Template String]
       |
       v
  [Lexer/Tokenizer] -> Splits into Text, Var, Block Tokens
       |
       v
    [Parser] -> Compiles tokens into AST (NodeList)
       |
       v
 [Node Execution] -> Evaluates AST against a Context
       |
       v
[Rendered HTML String]
```

## 2. Why It Exists
Separates presentation logic from Python business logic while providing safe evaluation (auto-escaping XSS by default) and easy inheritance without full Turing-completeness to prevent abuse.

## 3. Internal Working
Trace of `django/template/base.py`:
```python
class Template:
    def __init__(self, template_string, origin=None, name=None, engine=None):
        self.source = template_string
        self.engine = engine
        # Lexing
        lexer = Lexer(template_string)
        tokens = lexer.tokenize()
        # Parsing
        parser = Parser(tokens, engine.template_libraries, engine.builtins, origin)
        self.nodelist = parser.parse()

    def render(self, context):
        with context.bind_template(self):
            # Execution
            return self.nodelist.render(context)
```

## 4. Basic Implementation
```html
<!-- base.html -->
<html>
<body>
    {% block content %}{% endblock %}
</body>
</html>

<!-- child.html -->
{% extends "base.html" %}
{% block content %}
    <h1>Hello {{ user.username }}</h1>
{% endblock %}
```

## 5. Production-Ready Implementation
```python
# Custom Template Tag for Production (Avoids DB hits in templates)
from django import template
from django.core.cache import cache

register = template.Library()

@register.inclusion_tag('components/sidebar.html', takes_context=True)
def render_sidebar(context):
    request = context['request']
    cache_key = f"sidebar_{request.user.id}"
    data = cache.get(cache_key)
    if not data:
        data = expensive_db_query(request.user)
        cache.set(cache_key, data, 3600)
    return {'sidebar_data': data}
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Triggering N+1 queries in templates.
```html
<!-- BROKEN: Iterating triggers DB hit per item if prefetch_related wasn't used in view -->
{% for author in authors %}
    {{ author.profile.bio }} 
{% endfor %}
```

## 7. Environment-Specific Behavior
| Environment | Caching | Behavior |
|-------------|---------|----------|
| Local Dev | Disabled | Templates re-read from disk on every request. |
| Production | `cached.Loader` | AST is cached in memory. Changes require server restart. |

## 8. Local Development Issues
🔴 SYMPTOM: `TemplateDoesNotExist: app/template.html`
🔍 CAUSE: App not in `INSTALLED_APPS` or `APP_DIRS` is `False` in `TEMPLATES` config.
🔧 FIX: Check `settings.TEMPLATES` and `INSTALLED_APPS`.

## 9. Production Issues
INCIDENT: Dynamic Template Injection (Server-Side Template Injection).
SEVERITY: Critical
CAUSE: A developer used `Template(user_input).render(context)`. The attacker provided `{% load log %}{% log admin_password %}`.
FIX: NEVER compile templates from raw user input. Always use files loaded from secure directories.

## 10. Failure Simulation
```python
from django.template import Template, Context, TemplateSyntaxError
import pytest

def test_invalid_syntax_fails_fast():
    with pytest.raises(TemplateSyntaxError):
        Template("{% if x %} Missing endif")
```

## 11. Decision Matrix
| Need | Django Templates | Jinja2 |
|------|------------------|--------|
| Standard Admin/CRUD | ✅ Native | ❌ Complex setup |
| High Performance | ❌ Slower AST | ✅ Compiles to Python |

## 12. Senior-Level Questions
**Q: How does `{% extends %}` work internally?**
A: `ExtendsNode` parses the parent template, then swaps `BlockNode` elements in the parent's AST with matching `BlockNode` elements from the child's AST before final rendering.

## 13. Production Checklist
- [ ] `cached.Loader` is enabled (Django does this automatically if `DEBUG=False`).
- [ ] No DB queries executed in templates (use `select_related`/`prefetch_related` in view).
