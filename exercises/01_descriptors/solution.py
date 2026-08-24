from cryptography.fernet import Fernet

class EncryptedFieldDescriptor:
    def __init__(self, key: bytes):
        self.fernet = Fernet(key)
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        # Get the encrypted value from the instance's dictionary
        encrypted_value = instance.__dict__.get(self.name)
        if encrypted_value is None:
            return None
            
        # Decrypt and decode back to string
        return self.fernet.decrypt(encrypted_value).decode('utf-8')

    def __set__(self, instance, value):
        if value is None:
            instance.__dict__[self.name] = None
            return
            
        if not isinstance(value, str):
            raise ValueError("EncryptedFieldDescriptor only accepts strings.")
            
        # Encrypt the string and store in the instance's dictionary
        encrypted_value = self.fernet.encrypt(value.encode('utf-8'))
        instance.__dict__[self.name] = encrypted_value
