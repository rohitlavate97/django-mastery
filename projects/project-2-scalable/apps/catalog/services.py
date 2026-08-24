from django.core.cache import cache
from .models import Product
import time
import random

class CatalogService:
    @staticmethod
    def get_product_details(product_id):
        cache_key = f"product_details_{product_id}"
        data = cache.get(cache_key)
        
        if data is None:
            # Mutex stampede locking simulation
            lock_key = f"lock_{cache_key}"
            if cache.add(lock_key, "locked", 5):
                try:
                    product = Product.objects.select_related('category', 'inventory').get(id=product_id)
                    data = {
                        "id": product.id,
                        "name": product.name,
                        "price": str(product.price),
                        "stock": product.inventory.stock
                    }
                    cache.set(cache_key, data, timeout=300)
                finally:
                    cache.delete(lock_key)
            else:
                time.sleep(0.1)
                return CatalogService.get_product_details(product_id)
        
        return data
