# Exercise 03: Concurrency Race Condition

## Objective
Fix a critical race condition in a balance transfer / withdrawal mechanism.

## Context
A naive implementation of a withdrawal function looks like this:
```python
def withdraw(user_id, amount):
    account = Account.objects.get(user_id=user_id)
    if account.balance >= amount:
        account.balance -= amount
        account.save()
        return True
    return False
```
Under concurrent load (e.g., a user spamming the withdraw button), two requests might read the same balance, pass the check, and debit the account, leading to a negative balance.

## Requirements
Implement `safe_withdraw(user_id, amount)` in `solution.py`.
1. It must use database-level locking to prevent race conditions.
2. It must be atomic.
3. If the user doesn't have enough balance, it should raise a `ValueError("Insufficient funds")`.
4. It should return the updated balance upon success.

## Hints
- `transaction.atomic()`
- `select_for_update()`
