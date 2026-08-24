import pytest
from django.db import transaction, IntegrityError
from .solution import CustomUser, TaskQueue

@pytest.fixture(autouse=True)
def clear_tasks():
    TaskQueue.clear()
    yield

@pytest.mark.django_db(transaction=True)
def test_task_triggered_on_commit():
    with transaction.atomic():
        user = CustomUser.objects.create(username="testuser", email="test@example.com")
        
    # Transaction committed, tasks should be triggered
    assert len(TaskQueue.tasks) == 1
    assert TaskQueue.tasks[0] == user.id

@pytest.mark.django_db(transaction=True)
def test_task_not_triggered_on_rollback():
    try:
        with transaction.atomic():
            CustomUser.objects.create(username="testuser2", email="test2@example.com")
            raise ValueError("Simulated failure")
    except ValueError:
        pass
        
    # Transaction rolled back, tasks should NOT be triggered
    assert len(TaskQueue.tasks) == 0
