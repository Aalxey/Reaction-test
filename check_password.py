#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reactiontest.settings')
django.setup()

from django.contrib.auth.models import User

print("=== Database Password Check ===")
print()

# Get all users
users = User.objects.all()

if users.exists():
    print(f"Found {users.count()} user(s) in database:")
    print("-" * 50)
    
    for user in users:
        print(f"Username: {user.username}")
        print(f"Email: {user.email}")
        print(f"Password (as stored in DB): {user.password}")
        print(f"Password length: {len(user.password)}")
        print(f"Password starts with: {user.password[:20]}...")
        print("-" * 50)
else:
    print("No users found in database.")

print()
print("Note: The password field contains a cryptographic hash, not the plain text password.")
print("This is how Django securely stores passwords - the original password cannot be retrieved.") 