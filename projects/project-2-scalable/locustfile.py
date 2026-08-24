from locust import HttpUser, task, between

class ScalableAppUser(HttpUser):
    wait_time = between(1, 2)
    
    @task(3)
    def browse_catalog(self):
        self.client.get("/api/v1/catalog/1/")
        
    @task(1)
    def place_order(self):
        self.client.post("/api/v1/orders/", json={"product_id": 1, "quantity": 1})
