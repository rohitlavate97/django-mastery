from django.db import models
from apps.tenants.models import TenantModel

class Item(TenantModel):
    name = models.CharField(max_length=255)
    stock = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class Reservation(TenantModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='reservations')
    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} of {self.item.name}"
