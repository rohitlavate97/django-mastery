from django.db import models
from .context import get_current_tenant

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    schema_name = models.CharField(max_length=63, unique=True)
    is_active = models.BooleanField(default=True)
    plan_tier = models.CharField(max_length=50, default='free')

    def __str__(self):
        return self.name

class TenantDomain(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='domains', on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=True)

    def __str__(self):
        return self.domain

class TenantAwareQuerySet(models.QuerySet):
    def for_current_tenant(self):
        tenant = get_current_tenant()
        if tenant:
            return self.filter(tenant=tenant)
        return self

class TenantAwareManager(models.Manager):
    def get_queryset(self):
        return TenantAwareQuerySet(self.model, using=self._db).for_current_tenant()

class TenantModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
