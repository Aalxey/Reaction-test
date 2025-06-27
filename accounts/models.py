from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg
import uuid

# Create your models here.
class ReactionTestResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    time = models.FloatField()  # Time in seconds
    timestamp = models.DateTimeField(auto_now_add=True)
    is_for_leaderboard = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.user.username} - {self.time:.3f}s'

    class Meta:
        ordering = ['-timestamp']

class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    def __str__(self):
        return f'{self.user.username} at {self.timestamp}'

    class Meta:
        ordering = ['-timestamp']

class EvadeAndSequenceResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField()
    misses = models.IntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - {self.score}'

    class Meta:
        ordering = ['-timestamp']

class DeviceFingerprint(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fingerprint_hash = models.CharField(max_length=64, unique=True)
    device_name = models.CharField(max_length=100, blank=True)
    browser_info = models.TextField(blank=True)
    screen_resolution = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=10, blank=True)
    platform = models.CharField(max_length=50, blank=True)
    is_trusted = models.BooleanField(default=False)
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - {self.device_name}'

    class Meta:
        ordering = ['-last_used']

class UserOnlineStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    
    def __str__(self):
        status = "Online" if self.is_online else "Offline"
        return f'{self.user.username} - {status}'
    
    class Meta:
        verbose_name_plural = "User Online Statuses"
