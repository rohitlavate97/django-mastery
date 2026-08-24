import pytest
from cryptography.fernet import Fernet
from .solution import EncryptedFieldDescriptor

@pytest.fixture
def secret_key():
    return Fernet.generate_key()

def test_encrypted_field_descriptor(secret_key):
    class User:
        ssn = EncryptedFieldDescriptor(secret_key)
        
        def __init__(self, ssn):
            self.ssn = ssn

    # Test class-level access returns descriptor instance
    assert isinstance(User.ssn, EncryptedFieldDescriptor)
    
    # Test assignment and retrieval
    user = User("123-456-7890")
    assert user.ssn == "123-456-7890"
    
    # Verify the value is actually encrypted in the __dict__
    raw_stored_value = user.__dict__['ssn']
    assert raw_stored_value != "123-456-7890"
    assert isinstance(raw_stored_value, bytes)
    
    # Test setting None
    user.ssn = None
    assert user.ssn is None
    
    # Test validation
    with pytest.raises(ValueError):
        user.ssn = 12345
