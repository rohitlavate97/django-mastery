from django.db import models

class Account(models.Model):
    user_id = models.IntegerField(unique=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
