import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reactiontest.settings')
django.setup()

from django.contrib.auth.models import User

print("=== Users in Database ===")
users = User.objects.all()
if users.exists():
    for user in users:
        print(f"  - Username: {user.username}, Email: {user.email}")
else:
    print("No users found in database!")

print(f"\nTotal users: {users.count()}") 