from django.db import transaction
from .models import Account
from decimal import Decimal

def safe_withdraw(user_id: int, amount: Decimal) -> Decimal:
    """
    Safely withdraws the given amount from the user's account,
    preventing race conditions.
    
    Raises ValueError("Insufficient funds") if balance < amount.
    Returns the new balance.
    """
    with transaction.atomic():
        # select_for_update locks the row until the transaction completes
        account = Account.objects.select_for_update().get(user_id=user_id)
        
        if account.balance < amount:
            raise ValueError("Insufficient funds")
            
        account.balance -= amount
        account.save(update_fields=['balance'])
        
        return account.balance
