# 24-Hour Ranked Attempts Reset System

This system automatically resets users' ranked attempts after 24 hours, allowing them to get 3 new ranked attempts daily.

## How It Works

1. **When a user completes a ranked attempt**, a timestamp is recorded in the `ranked_attempt_timestamp` field.
2. **The system only counts attempts from the last 24 hours** when determining if a user can make ranked attempts.
3. **Expired attempts (older than 24 hours) are automatically reset** to practice mode.

## Database Changes

- Added `ranked_attempt_timestamp` field to `ReactionTestResult` model
- This field stores when each ranked attempt was made

## Manual Commands

### Check for expired attempts (dry run):
```bash
python manage.py reset_expired_ranked_attempts --dry-run
```

### Reset expired attempts:
```bash
python manage.py reset_expired_ranked_attempts
```

## Automatic Execution Setup

### Option 1: Cron Job (Linux/Mac)
Add to your crontab to run every hour:
```bash
0 * * * * cd /path/to/your/project && python manage.py reset_expired_ranked_attempts
```

### Option 2: Windows Task Scheduler
1. Open Task Scheduler
2. Create a new Basic Task
3. Set it to run daily at a specific time
4. Action: Start a program
5. Program: `python`
6. Arguments: `manage.py reset_expired_ranked_attempts`
7. Start in: `C:\path\to\your\project`

### Option 3: Django Management Command with Celery
If you're using Celery, you can create a periodic task:
```python
# In your Celery configuration
CELERY_BEAT_SCHEDULE = {
    'reset-ranked-attempts': {
        'task': 'accounts.tasks.reset_expired_ranked_attempts',
        'schedule': crontab(hour='*/1'),  # Every hour
    },
}
```

## Testing the System

1. **Create a test user** and make 3 ranked attempts
2. **Wait 24 hours** (or manually update timestamps in database)
3. **Run the reset command** to see expired attempts being reset
4. **Verify the user can now make ranked attempts again**

## Database Queries for Monitoring

### Check current ranked attempts for a user:
```sql
SELECT COUNT(*) FROM accounts_reactiontestresult 
WHERE user_id = [USER_ID] 
AND is_for_leaderboard = 1 
AND ranked_attempt_timestamp >= datetime('now', '-24 hours');
```

### Check expired attempts:
```sql
SELECT * FROM accounts_reactiontestresult 
WHERE is_for_leaderboard = 1 
AND ranked_attempt_timestamp < datetime('now', '-24 hours');
```

## Notes

- The system is designed to be safe and can be run multiple times without issues
- Use `--dry-run` flag to see what would be reset without making changes
- The reset only affects attempts older than 24 hours
- Users will see their remaining attempts update immediately after the reset 