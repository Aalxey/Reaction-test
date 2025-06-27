from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import LoginHistory

@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    """
    Record user login time.
    """
    LoginHistory.objects.create(user=user) 