from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

# Dummy task for simulation
class TaskQueue:
    tasks = []
    
    @classmethod
    def delay(cls, user_id):
        cls.tasks.append(user_id)
        
    @classmethod
    def clear(cls):
        cls.tasks = []

class CustomUser(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    
    class Meta:
        app_label = 'exercises'

@receiver(post_save, sender=CustomUser)
def send_welcome_email(sender, instance, created, **kwargs):
    if created:
        # WRONG WAY: TaskQueue.delay(instance.id)
        # RIGHT WAY: Use on_commit
        transaction.on_commit(lambda: TaskQueue.delay(instance.id))
