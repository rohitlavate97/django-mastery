import pytest
import concurrent.futures
from decimal import Decimal
from django.db import connection, transaction
from .models import Account
from .solution import safe_withdraw

@pytest.fixture
def account(db):
    return Account.objects.create(user_id=1, balance=Decimal('100.00'))

@pytest.mark.django_db(transaction=True)
def test_concurrent_withdrawals(account):
    # We want to withdraw 10 from the account 20 times concurrently.
    # The balance is 100, so exactly 10 should succeed and 10 should fail.
    
    amount = Decimal('10.00')
    success_count = 0
    failure_count = 0
    
    # In SQLite, concurrent writes might throw OperationalError, but select_for_update()
    # combined with atomic() helps serialize transactions. If errors happen, we catch them.
    # Note: To avoid 'database is locked' errors on SQLite for this test, 
    # we might need to tweak the timeout, but let's test the logic.
    
    def worker():
        try:
            # We need to make sure each thread gets its own db connection logic in Django 
            # if we were not using transaction=True, but transaction=True creates a real DB
            safe_withdraw(1, amount)
            return True
        except ValueError: # Insufficient funds
            return False
        except Exception as e:
            # OperationalError might happen in SQLite under heavy concurrency, 
            # but in a real DB (Postgres) it would queue or timeout.
            return False
        finally:
            connection.close()
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(worker) for _ in range(20)]
        results = [f.result() for f in futures]
        
    success_count = sum(1 for r in results if r is True)
    
    # Verify the database state
    account.refresh_from_db()
    
    assert account.balance == Decimal('0.00')
    assert success_count == 10
