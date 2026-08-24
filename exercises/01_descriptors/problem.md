# Exercise 01: Python Descriptors (Encrypted Field)

## Objective
Implement a Python Descriptor (`EncryptedFieldDescriptor`) that automatically encrypts string data when assigned (set) to a class attribute, and decrypts it when accessed (get).

## Requirements
1. The descriptor must implement `__get__`, `__set__`, and `__set_name__`.
2. When accessed from the class (e.g., `MyModel.secret`), it must return the descriptor instance itself.
3. When set on an instance (`obj.secret = "hello"`), it should store the *encrypted* value in the instance's `__dict__`.
4. When accessed from an instance (`print(obj.secret)`), it should return the *decrypted* value.
5. Use the `cryptography.fernet.Fernet` library for encryption/decryption (a key will be provided).

## Hints
- `__set_name__(self, owner, name)` is used to know the attribute name.
- `__get__(self, instance, owner)` handles attribute access.
- `__set__(self, instance, value)` handles attribute assignment.
- Remember to encode strings to bytes before encryption, and decode them after decryption.
