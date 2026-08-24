from celery import shared_task
import time

@shared_task
def send_order_confirmation_email(order_id):
    # Simulate sending email
    time.sleep(2)
    return f"Email sent for order {order_id}"

@shared_task
def generate_invoice(order_id):
    # Simulate PDF generation
    time.sleep(3)
    return f"Invoice generated for order {order_id}"
