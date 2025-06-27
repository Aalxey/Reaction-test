from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Count
from accounts.models import ReactionTestResult, EvadeAndSequenceResult, LoginHistory, DeviceFingerprint


class Command(BaseCommand):
    help = 'Clean up duplicate users with the same email address'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find users with duplicate emails
        duplicate_emails = User.objects.values('email').annotate(
            count=Count('email')
        ).filter(count__gt=1, email__isnull=False)
        
        if not duplicate_emails:
            self.stdout.write(self.style.SUCCESS('No duplicate emails found!'))
            return
        
        self.stdout.write(f'Found {len(duplicate_emails)} email(s) with duplicates:')
        
        total_deleted = 0
        
        for email_data in duplicate_emails:
            email = email_data['email']
            count = email_data['count']
            
            self.stdout.write(f'\nEmail: {email} ({count} users)')
            
            # Get all users with this email
            users = User.objects.filter(email=email).order_by('date_joined')
            
            # Keep the oldest user (first created)
            keep_user = users.first()
            delete_users = users[1:]
            
            self.stdout.write(f'  Keeping: {keep_user.username} (ID: {keep_user.id}, Created: {keep_user.date_joined})')
            
            for user in delete_users:
                self.stdout.write(f'  Will delete: {user.username} (ID: {user.id}, Created: {user.date_joined})')
                
                if not dry_run:
                    # Transfer data from duplicate user to keep user
                    self.transfer_user_data(user, keep_user)
                    
                    # Delete the duplicate user
                    user.delete()
                    total_deleted += 1
                    self.stdout.write(f'    ✓ Deleted user {user.username}')
                else:
                    self.stdout.write(f'    Would transfer data and delete user {user.username}')
        
        if dry_run:
            self.stdout.write(f'\n{self.style.WARNING("DRY RUN SUMMARY:")} Would delete {total_deleted} duplicate user(s)')
        else:
            self.stdout.write(f'\n{self.style.SUCCESS("CLEANUP COMPLETE:")} Deleted {total_deleted} duplicate user(s)')
    
    def transfer_user_data(self, from_user, to_user):
        """Transfer all data from one user to another"""
        
        # Transfer ReactionTestResult
        reaction_count = ReactionTestResult.objects.filter(user=from_user).count()
        if reaction_count > 0:
            ReactionTestResult.objects.filter(user=from_user).update(user=to_user)
            self.stdout.write(f'    ✓ Transferred {reaction_count} reaction test results')
        
        # Transfer EvadeAndSequenceResult
        evade_count = EvadeAndSequenceResult.objects.filter(user=from_user).count()
        if evade_count > 0:
            EvadeAndSequenceResult.objects.filter(user=from_user).update(user=to_user)
            self.stdout.write(f'    ✓ Transferred {evade_count} evade and sequence results')
        
        # Transfer LoginHistory
        login_count = LoginHistory.objects.filter(user=from_user).count()
        if login_count > 0:
            LoginHistory.objects.filter(user=from_user).update(user=to_user)
            self.stdout.write(f'    ✓ Transferred {login_count} login history records')
        
        # Transfer DeviceFingerprint
        device_count = DeviceFingerprint.objects.filter(user=from_user).count()
        if device_count > 0:
            DeviceFingerprint.objects.filter(user=from_user).update(user=to_user)
            self.stdout.write(f'    ✓ Transferred {device_count} device fingerprint records') 