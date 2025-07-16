import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
import socket
from .models import UserOnlineStatus
from django.utils import timezone

logger = logging.getLogger(__name__)

class UserOnlineStatusMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Update user's online status
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                status, created = UserOnlineStatus.objects.get_or_create(
                    user=request.user,
                    defaults={'is_online': True, 'session_key': request.session.session_key}
                )
                if not created:
                    status.is_online = True
                    status.session_key = request.session.session_key
                    status.last_seen = timezone.now()
                    status.save()
            except Exception as e:
                logger.error(f"Error updating user online status: {e}")

    def process_response(self, request, response):
        return response

class BrokenPipeMiddleware(MiddlewareMixin):
    """
    Middleware to handle broken pipe errors gracefully.
    """
    def process_request(self, request):
        return None

    def process_response(self, request, response):
        return response

    def process_exception(self, request, exception):
        # Handle broken pipe errors
        if isinstance(exception, (socket.error, ConnectionResetError, BrokenPipeError)):
            logger.warning(f"Broken pipe error handled gracefully: {exception}")
            return HttpResponse(b"Connection closed", status=499)  # Client Closed Request
        return None 