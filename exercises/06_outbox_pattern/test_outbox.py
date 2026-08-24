import pytest
from unittest.mock import Mock
from django.db import transaction, IntegrityError
from .solution import OutboxEvent, publish_event, OutboxRelay

@pytest.mark.django_db
def test_outbox_event_created_in_transaction():
    with transaction.atomic():
        publish_event("Order", "123", "OrderCreated", {"amount": 100})
    
    assert OutboxEvent.objects.count() == 1
    event = OutboxEvent.objects.first()
    assert event.aggregate_type == "Order"
    assert not event.processed

@pytest.mark.django_db
def test_outbox_rollback_on_failure():
    try:
        with transaction.atomic():
            publish_event("Order", "123", "OrderCreated", {"amount": 100})
            raise ValueError("Simulate DB failure")
    except ValueError:
        pass
    
    assert OutboxEvent.objects.count() == 0

@pytest.mark.django_db
def test_outbox_relay_processing():
    publish_event("Order", "123", "OrderCreated", {"amount": 100})
    
    mock_publisher = Mock()
    relay = OutboxRelay(mock_publisher)
    
    relay.process_events()
    
    mock_publisher.assert_called_once_with("Order", "123", "OrderCreated", {"amount": 100})
    event = OutboxEvent.objects.first()
    assert event.processed
