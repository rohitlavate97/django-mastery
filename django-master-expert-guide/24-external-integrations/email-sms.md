# Transactional Email and SMS in Django

## 1. Mental Model
```text
[Django View/Model] -> (Transaction Commit) -> [Celery Message Broker]
                                                       |
                                              [Celery Worker Task]
                                                       |
                                        [Email/SMS API (SendGrid/Twilio)]
```
Transactional messaging must be asynchronous and transaction-aware. If you send an email synchronously during a web request, a slow API will block the user. If you send it asynchronously *before* the database commits, the Celery task might execute before the data exists!

## 2. Why It Exists
Users expect immediate confirmation for actions (signups, purchases, password resets). Offloading this to a background worker ensures the web response is lightning fast, while robust retries ensure the message is delivered even if the external provider has a temporary outage.

## 3. Internal Working
Django's `django.core.mail.send_mail` is synchronous by default. It opens an SMTP connection, sends the message, and waits for confirmation.
To make it async, we wrap it in a Celery task. To make it safe, we trigger that task using `transaction.on_commit()`, which hooks into Django's database transaction lifecycle and only executes the callback if the transaction is successfully committed to the DB.

## 4. Basic Implementation
```python
# 🔴 ANTI-PATTERN: Sync email + no transaction awareness
from django.core.mail import send_mail

def create_user_bad(request):
    user = User.objects.create(email="test@example.com")
    # BAD 1: Blocks the web response for ~1 second.
    # BAD 2: If the DB transaction fails later, the user still gets the email!
    send_mail("Welcome!", "Hello.", "from@us.com", [user.email])
    return HttpResponse("User created")
```

## 5. Production-Ready Implementation
```python
# ✅ PRODUCTION-READY
from django.db import transaction
from django.core.mail import EmailMultiAlternatives
from celery import shared_task

# 1. The Async Task (with retries)
@shared_task(bind=True, max_retries=3)
def send_welcome_email_task(self, user_id):
    try:
        user = User.objects.get(id=user_id)
        
        subject = "Welcome to Our Platform!"
        text_content = f"Hi {user.first_name}, welcome!"
        html_content = f"<p>Hi <strong>{user.first_name}</strong>, welcome!</p>"
        
        msg = EmailMultiAlternatives(subject, text_content, "noreply@us.com", [user.email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
    except Exception as exc:
        # Retry with exponential backoff if the SMTP server is down
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

# 2. The View Logic (Transaction Aware)
def register_user(request):
    with transaction.atomic():
        user = User.objects.create(
            email="test@example.com",
            first_name="Alice"
        )
        
        # This lambda will ONLY execute if the outer transaction commits.
        # It guarantees the Celery worker will be able to find the User.
        transaction.on_commit(
            lambda: send_welcome_email_task.delay(user.id)
        )
        
    return HttpResponse("Registered successfully")
```

## 6. Anti-Patterns
🔴 **Passing ORM Objects to Celery:** Passing `user` instead of `user.id`. Celery serializes arguments via JSON/Pickle. If you pass an object, it might be stale by the time the task runs, or fail to serialize.
🔴 **Sending inside signals:** Triggering emails directly inside `post_save` signals without `on_commit`, leading to the exact same race conditions.

## 7. Environment-Specific Behavior
| Environment | Email Backend | Consideration |
|-------------|---------------|---------------|
| Local | `django.core.mail.backends.console.EmailBackend` or Mailpit | Prints to console or traps in local UI. |
| Testing | `django.core.mail.backends.locmem.EmailBackend` | Accessible via `mail.outbox`. |
| Production | `Anymail` (SendGrid/Mailgun) or SMTP | Requires verified domains and DKIM/SPF setup. |

## 8. Local Development Issues
🔴 **SYMPTOM:** Celery worker raises `User.DoesNotExist` immediately after you create a user via an API.
🔍 **CAUSE:** You used `.delay(user.id)` inside a transaction without `on_commit()`. Celery is so fast it tried to query the DB before the web process committed the row!
🔧 **FIX:** Wrap the `.delay()` call in `transaction.on_commit()`.

## 9. Production Issues
🔴 **INCIDENT:** Users received 15 duplicate welcome emails.
* **Severity:** Medium
* **Investigation:** The email provider's API was extremely slow, taking 65 seconds to respond. The Celery worker had a hard time limit of 60 seconds. The worker killed the task (raising an exception), but the provider *did* actually send the email. Celery retried the task, repeating the process.
* **Root Cause:** Missing timeouts on the SMTP client or API client, and non-idempotent task retries.
* **Fix:** Enforced a strict 5-second timeout on the email API client.

## 10. Failure Simulation
To test the transaction race condition, remove `transaction.on_commit()`, and add `time.sleep(2)` at the very end of your view (before returning the response). The Celery worker will crash trying to find the object.

## 11. Decision Matrix
| Provider | Integration | Pros | Cons |
|----------|-------------|------|------|
| Native SMTP | `django.core.mail` | Standard, works with everything | Slow, manual bounce handling |
| Anymail (API) | `django-anymail` | Lightning fast, parses webhooks for bounces | Vendor specific (though Anymail abstracts this well) |

## 12. Senior-Level Questions
**Q: How do you handle a scenario where SendGrid is entirely down for 4 hours, and you have thousands of critical transactional emails backing up?**
A: Use a Fallback Routing strategy. In your Celery task, catch `AnymailAPIError`. If the error indicates a 5xx server issue, switch the backend dynamically to a secondary provider (e.g., Mailgun) and retry immediately. If all providers fail, rely on Celery's exponential backoff.

## 13. Production Checklist
- [ ] ALL async task triggers that rely on new DB records use `transaction.on_commit()`.
- [ ] Email backends strictly use APIs instead of raw SMTP where possible (via Anymail) for speed.
- [ ] Celery tasks accept primary keys (IDs), never full ORM instances.
- [ ] Sender domains have verified SPF, DKIM, and DMARC records.
