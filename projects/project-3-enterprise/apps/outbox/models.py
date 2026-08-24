from django.db import models
import uuid

class OutboxMessage(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PUBLISHED', 'Published'),
        ('FAILED', 'Failed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=255)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event_type} - {self.status}"
