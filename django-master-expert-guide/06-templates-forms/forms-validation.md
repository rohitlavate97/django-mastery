# Forms Validation Internals [DJANGO 6.1+]

## 1. Mental Model
```text
[POST Data (QueryDict)]
        |
        v
    Form(data=POST)
        |
        v
   is_valid() -> full_clean()
        |
  [Field Clean (clean_<field>)] --> Validates type, runs field-level regex.
        |
  [Form Clean (clean)] --> Validates cross-field dependencies (e.g., password == confirm_password).
        |
        v
[ cleaned_data / errors ]
```

## 2. Why It Exists
Sanitizes raw HTTP string payloads into Python types, validates business logic, and generates safe HTML inputs.

## 3. Internal Working
Trace of `django/forms/forms.py`:
```python
class BaseForm:
    def full_clean(self):
        self._errors = ErrorDict()
        if not self.is_bound:
            return
        self.cleaned_data = {}
        # 1. Clean individual fields
        self._clean_fields()
        # 2. Clean cross-field dependencies
        self._clean_form()
        # 3. Post-clean hooks
        self._post_clean()
        
    def _clean_fields(self):
        for name, field in self.fields.items():
            try:
                value = field.clean(self.data.get(name))
                self.cleaned_data[name] = value
                if hasattr(self, f'clean_{name}'):
                    self.cleaned_data[name] = getattr(self, f'clean_{name}')()
            except ValidationError as e:
                self.add_error(name, e)
```

## 4. Basic Implementation
```python
from django import forms

class ContactForm(forms.Form):
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)
```

## 5. Production-Ready Implementation
```python
from django import forms
from django.core.exceptions import ValidationError
import re

class SecureRegistrationForm(forms.Form):
    username = forms.CharField(max_length=50)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not re.match(r'^\w+$', username):
            raise ValidationError("Username must be alphanumeric.")
        # DB check (ensure efficient query)
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Username taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if pwd and confirm and pwd != confirm:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Mutating `data` instead of `cleaned_data`.
```python
class BadForm(forms.Form):
    def clean(self):
        # BROKEN: QueryDict is immutable, this crashes or modifies raw payload unsafely.
        self.data['email'] = self.data['email'].lower() 
```

## 7. Environment-Specific Behavior
Forms run identically across environments. Performance differences arise from DB queries inside `clean()` during heavy load.

## 8. Local Development Issues
🔴 SYMPTOM: `clean_email()` never executes.
🔍 CAUSE: The base field validation (e.g., `EmailField`) failed first. Django skips custom `clean_<field>` if the basic field `clean()` raises `ValidationError`.
🔧 FIX: Handle valid data conditionally or fix the base field rules.

## 9. Production Issues
INCIDENT: Server lockup during user import via forms.
SEVERITY: High
CAUSE: Form was instantiated inside a loop of 10,000 rows. `ModelChoiceField` queried the database on every instantiation.
FIX: Cache the queryset or use bulk DB operations instead of instantiating forms in batch loops.

## 10. Failure Simulation
```python
def test_form_validation():
    form = SecureRegistrationForm(data={'username': 'admin!', 'password': '1', 'confirm_password': '2'})
    assert not form.is_valid()
    assert 'username' in form.errors
    assert 'confirm_password' in form.errors
```

## 11. Decision Matrix
| Tool | Best For | Cons |
|------|----------|------|
| Django Forms | SSR HTML forms | Clunky for JSON APIs |
| DRF Serializers | JSON APIs, nested data | Heavy dependency |
| Pydantic | Fast JSON validation | No HTML rendering |

## 12. Senior-Level Questions
**Q: How does `ModelForm` differ in `full_clean()`?**
A: `ModelForm` overrides `_post_clean()` to call `self.instance.clean()` and `self.instance.validate_unique()`, mapping model-level validation errors back to the form fields.

## 13. Production Checklist
- [ ] No heavy DB queries in `__init__` (especially for `ChoiceField`).
- [ ] Cross-field errors correctly added via `add_error()` instead of raising raw exceptions.
