from django.utils import timezone
from django.contrib.auth.models import User
from .models import UserOnlineStatus
from datetime import timedelta

class UserOnlineStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request
        response = self.get_response(request)
        
        # Update online status after response is processed
        self.update_user_status(request)
        
        return response
    
    def update_user_status(self, request):
        if request.user.is_authenticated:
            # Get or create user status
            status, created = UserOnlineStatus.objects.get_or_create(
                user=request.user,
                defaults={
                    'is_online': True,
                    'session_key': request.session.session_key
                }
            )
            
            if not created:
                # Update existing status
                status.is_online = True
                status.last_seen = timezone.now()
                status.session_key = request.session.session_key
                status.save()
        
        # Clean up old offline users (every 5 minutes)
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        UserOnlineStatus.objects.filter(
            last_seen__lt=five_minutes_ago,
            is_online=True
        ).update(is_online=False) 