from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import ReactionTestResult
from django.db import models


class Command(BaseCommand):
    help = 'Reset expired ranked attempts (older than 24 hours) to practice mode'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually resetting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Calculate cutoff time (24 hours ago)
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        # Find expired ranked attempts
        expired_attempts = ReactionTestResult.objects.filter(
            is_for_leaderboard=True,
            ranked_attempt_timestamp__lt=cutoff_time
        )
        
        if not expired_attempts.exists():
            self.stdout.write(self.style.SUCCESS('No expired ranked attempts found!'))
            return
        
        # Group by user for better reporting
        users_with_expired = expired_attempts.values('user__username').distinct()
        
        self.stdout.write(f'Found {expired_attempts.count()} expired ranked attempts for {len(users_with_expired)} users:')
        
        total_reset = 0
        
        for user_data in users_with_expired:
            username = user_data['user__username']
            user_expired = expired_attempts.filter(user__username=username)
            count = user_expired.count()
            
            self.stdout.write(f'\nUser: {username} ({count} expired attempts)')
            
            for attempt in user_expired:
                self.stdout.write(f'  - Attempt from {attempt.ranked_attempt_timestamp} ({attempt.time:.3f}s)')
                
                if not dry_run:
                    attempt.is_for_leaderboard = False
                    attempt.save()
                    total_reset += 1
                    self.stdout.write(f'    ✓ Reset to practice mode')
                else:
                    self.stdout.write(f'    Would reset to practice mode')
        
        if dry_run:
            self.stdout.write(f'\n{self.style.WARNING("DRY RUN SUMMARY:")} Would reset {total_reset} expired ranked attempts')
        else:
            self.stdout.write(f'\n{self.style.SUCCESS("RESET COMPLETE:")} Reset {total_reset} expired ranked attempts')
            
            # Show users who now have ranked attempts available
            active_ranked_attempts = ReactionTestResult.objects.filter(
                is_for_leaderboard=True,
                ranked_attempt_timestamp__gte=cutoff_time
            )
            
            users_with_available = active_ranked_attempts.values('user__username').annotate(
                count=models.Count('id')
            ).filter(count__lt=3)
            
            if users_with_available:
                self.stdout.write(f'\nUsers who now have ranked attempts available:')
                for user_data in users_with_available:
                    username = user_data['user__username']
                    count = user_data['count']
                    remaining = 3 - count
                    self.stdout.write(f'  - {username}: {remaining} attempts remaining') 