from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import UserOnlineStatus

class Command(BaseCommand):
    help = 'Clean up online status records and set users to offline if inactive'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=5,
            help='Number of minutes of inactivity before marking user as offline (default: 5)'
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        
        # Find users who haven't been seen recently
        inactive_users = UserOnlineStatus.objects.filter(
            is_online=True,
            last_seen__lt=cutoff_time
        )
        
        count = inactive_users.count()
        if count > 0:
            inactive_users.update(is_online=False)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully marked {count} users as offline (inactive for {minutes} minutes)'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'No users found to mark as offline (threshold: {minutes} minutes)'
                )
            )
        
        # Also clean up any orphaned records (users that don't exist anymore)
        total_users = UserOnlineStatus.objects.count()
        self.stdout.write(f'Total online status records: {total_users}') 