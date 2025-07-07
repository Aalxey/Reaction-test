from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from .forms import SignUpForm, LoginForm
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import ReactionTestResult, LoginHistory, EvadeAndSequenceResult, DeviceFingerprint, UserOnlineStatus
import json
from django.db import models
from django.db.models import Avg
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import timedelta
from django.utils import timezone
import hashlib
import re
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache

# Create your views here.

def generate_device_fingerprint(request):
    """Generate a unique device fingerprint from available browser information"""
    # Get client IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    # Get user agent
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Get additional headers that can help identify the device
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    accept = request.META.get('HTTP_ACCEPT', '')
    
    # Create a fingerprint string
    fingerprint_string = f"{ip}|{user_agent}|{accept_language}|{accept_encoding}|{accept}"
    
    # Generate hash
    fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    return fingerprint_hash, {
        'ip_address': ip,
        'user_agent': user_agent,
        'accept_language': accept_language,
        'accept_encoding': accept_encoding,
        'accept': accept
    }

def auto_login_view(request):
    """Auto-login view that checks device fingerprint"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Check for auto-login
    auto_login_user = check_auto_login(request)
    if auto_login_user:
        return redirect('dashboard')
    else:
        # No trusted device found, redirect to login
        return redirect('login')

def signup_view(request):
    # If user is already authenticated, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Check for auto-login first if user is not authenticated
    if not request.user.is_authenticated:
        auto_login_user = check_auto_login(request)
        if auto_login_user:
            return redirect('dashboard')
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        remember_device = request.POST.get('remember_device') == 'on'
        
        # Create a username from the full name (remove spaces, lowercase)
        username = full_name.replace(' ', '').lower()
        
        # Handle empty full name
        if not username:
            messages.error(request, 'Full Name cannot be empty.')
            return render(request, 'accounts/signup.html')

        # Split full name into first and last name
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        print(f"DEBUG: Signup attempt - Full Name: '{full_name}', Email: '{email}', Generated Username: '{username}'")
        
        if password == confirm_password:
            if User.objects.filter(username=username).exists():
                print(f"DEBUG: Username '{username}' already exists.")
                messages.error(request, f"A user with the name '{full_name}' already exists. Please choose a different name.")
            elif User.objects.filter(email=email).exists():
                print(f"DEBUG: Email already registered: {email}")
                messages.error(request, 'Email already registered.')
            else:
                print(f"DEBUG: Creating new user: {username}")
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                print(f"DEBUG: User created successfully: {user.username} (ID: {user.id})")
                login(request, user)
                
                # Generate device fingerprint
                fingerprint_hash, device_info = generate_device_fingerprint(request)
                
                # If user wants to remember this device
                if remember_device:
                    # Check if device already exists
                    device, created = DeviceFingerprint.objects.get_or_create(
                        fingerprint_hash=fingerprint_hash,
                        defaults={
                            'user': user,
                            'device_name': f"{user.first_name}'s Device",
                            'browser_info': device_info['user_agent'],
                            'is_trusted': True
                        }
                    )
                    
                    if not created:
                        # Update existing device
                        device.user = user
                        device.is_trusted = True
                        device.last_used = timezone.now()
                        device.save()
                    
                    messages.success(request, 'Account created successfully! Device remembered for future auto-login!')
                else:
                    messages.success(request, 'Account created successfully!')
                
                # Log the login
                LoginHistory.objects.create(
                    user=user,
                    ip_address=device_info['ip_address'],
                    user_agent=device_info['user_agent']
                )
                
                print(f"DEBUG: Redirecting to dashboard after signup")
                return redirect('dashboard')
        else:
            print(f"DEBUG: Passwords do not match")
            messages.error(request, 'Passwords do not match.')
    
    return render(request, 'accounts/signup.html')

def login_view(request):
    # If user is already authenticated, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Check for auto-login first if user is not authenticated
    if not request.user.is_authenticated:
        auto_login_user = check_auto_login(request)
        if auto_login_user:
            return redirect('dashboard')
    
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        remember_device = request.POST.get('remember_device') == 'on'
        
        print(f"DEBUG: Login attempt - Username/Email: {username_or_email}")
        
        user = None
        error_message = None
        if '@' in username_or_email:
            user_obj = User.objects.filter(email=username_or_email).first()
            if not user_obj:
                error_message = 'No account found with this email.'
            else:
                user = authenticate(request, username=user_obj.username, password=password)
                if not user:
                    error_message = 'Incorrect password for this email.'
        else:
            user_obj = User.objects.filter(username=username_or_email).first()
            if not user_obj:
                error_message = 'No account found with this username.'
            else:
                user = authenticate(request, username=username_or_email, password=password)
                if not user:
                    error_message = 'Incorrect password for this username.'
        
        print(f"DEBUG: Authentication result - User: {user}")
        
        if user is not None:
            login(request, user)
            print(f"DEBUG: User logged in successfully: {user.username}")
            
            # Generate device fingerprint
            fingerprint_hash, device_info = generate_device_fingerprint(request)
            
            # If user wants to remember this device
            if remember_device:
                # Check if device already exists
                device, created = DeviceFingerprint.objects.get_or_create(
                    fingerprint_hash=fingerprint_hash,
                    defaults={
                        'user': user,
                        'device_name': f"{user.first_name}'s Device",
                        'browser_info': device_info['user_agent'],
                        'is_trusted': True
                    }
                )
                
                if not created:
                    # Update existing device
                    device.user = user
                    device.is_trusted = True
                    device.last_used = timezone.now()
                    device.save()
                
                messages.success(request, 'Device remembered for future auto-login!')
            
            # Log the login
            LoginHistory.objects.create(
                user=user,
                ip_address=device_info['ip_address'],
                user_agent=device_info['user_agent']
            )
            
            print(f"DEBUG: Redirecting to dashboard")
            return redirect('dashboard')
        else:
            print(f"DEBUG: Authentication failed")
            if error_message:
                messages.error(request, error_message)
            else:
                messages.error(request, 'Invalid login credentials.')
    
    return render(request, 'accounts/login.html')

def check_auto_login(request):
    """Helper function to check if auto-login should be attempted"""
    # Generate device fingerprint
    fingerprint_hash, device_info = generate_device_fingerprint(request)
    
    # Check if we have a trusted device for this fingerprint
    try:
        device = DeviceFingerprint.objects.get(
            fingerprint_hash=fingerprint_hash,
            is_trusted=True
        )
        
        # Auto-login the user
        login(request, device.user)
        
        # Update last used timestamp
        device.last_used = timezone.now()
        device.save()
        
        # Log the login
        LoginHistory.objects.create(
            user=device.user,
            ip_address=device_info['ip_address'],
            user_agent=device_info['user_agent']
        )
        
        messages.success(request, f'Welcome back, {device.user.first_name}! Auto-logged in from your trusted device.')
        return device.user
        
    except DeviceFingerprint.DoesNotExist:
        return None

@login_required
def dashboard_view(request):
    user = request.user
    # User stats - only using ranked scores
    user_results = ReactionTestResult.objects.filter(user=user, is_for_leaderboard=True)
    best_time = user_results.order_by('time').first().time * 1000 if user_results.exists() else None
    
    # Total tests completed can include all tests
    tests_completed = ReactionTestResult.objects.filter(user=user).count()

    # Global stats - only using ranked scores
    fastest_result = ReactionTestResult.objects.filter(is_for_leaderboard=True).order_by('time').select_related('user').first()
    if fastest_result:
        fastest_user = {
            'name': f'{fastest_result.user.first_name} {fastest_result.user.last_name}',
            'username': f'@{fastest_result.user.username}',
            'time': int(fastest_result.time * 1000),
            'avatar': 'https://randomuser.me/api/portraits/men/32.jpg',  # Placeholder avatar
            'tagline': 'Lightning Fast!'
        }
    else:
        fastest_user = None
        
    # Global rank (1-based) - only using ranked scores
    global_rank = None
    if best_time is not None:
        # Get each user's best ranked time
        user_best_times = ReactionTestResult.objects.filter(is_for_leaderboard=True)\
            .values('user_id').annotate(best_time=models.Min('time')).order_by('best_time')
        
        sorted_user_ids = [entry['user_id'] for entry in user_best_times]
        
        if user.id in sorted_user_ids:
            global_rank = sorted_user_ids.index(user.id) + 1

    context = {
        'fastest_user': fastest_user,
        'best_time': int(best_time) if best_time is not None else None,
        'tests_completed': tests_completed,
        'global_rank': global_rank,
    }
    return render(request, 'accounts/dashboard.html', context)

@login_required
def leaderboard_view(request):
    # Get time filter from request, default to 'all'
    time_filter = request.GET.get('time', 'all')
    
    # Calculate time thresholds
    from datetime import datetime, timedelta
    now = timezone.now()
    
    if time_filter == 'day':
        # Set start_date to midnight of the current day
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_filter == 'week':
        start_date = now - timedelta(weeks=1)
    else:  # 'all' or any other value
        start_date = None
    
    # Calculate progress data for current user
    user_progress = {}
    if request.user.is_authenticated:
        # Current week (last 7 days)
        current_week_start = now - timedelta(weeks=1)
        # Previous week (7 days before that)
        previous_week_start = now - timedelta(weeks=2)
        previous_week_end = current_week_start
        
        # Reaction Test Progress
        current_week_reaction = ReactionTestResult.objects.filter(
            user=request.user,
            is_for_leaderboard=True,
            timestamp__gte=current_week_start
        ).aggregate(best_time=models.Min('time'))
        
        previous_week_reaction = ReactionTestResult.objects.filter(
            user=request.user,
            is_for_leaderboard=True,
            timestamp__gte=previous_week_start,
            timestamp__lt=previous_week_end
        ).aggregate(best_time=models.Min('time'))
        
        if current_week_reaction['best_time'] and previous_week_reaction['best_time']:
            reaction_improvement = (previous_week_reaction['best_time'] - current_week_reaction['best_time']) * 1000  # Convert to ms
            reaction_improvement_percent = ((previous_week_reaction['best_time'] - current_week_reaction['best_time']) / previous_week_reaction['best_time']) * 100
        else:
            reaction_improvement = None
            reaction_improvement_percent = None
        
        # Evade & Sequence Progress
        current_week_evade = EvadeAndSequenceResult.objects.filter(
            user=request.user,
            timestamp__gte=current_week_start
        ).aggregate(best_score=models.Max('score'))
        
        previous_week_evade = EvadeAndSequenceResult.objects.filter(
            user=request.user,
            timestamp__gte=previous_week_start,
            timestamp__lt=previous_week_end
        ).aggregate(best_score=models.Max('score'))
        
        if current_week_evade['best_score'] and previous_week_evade['best_score']:
            evade_improvement = current_week_evade['best_score'] - previous_week_evade['best_score']
            evade_improvement_percent = ((current_week_evade['best_score'] - previous_week_evade['best_score']) / previous_week_evade['best_score']) * 100
        else:
            evade_improvement = None
            evade_improvement_percent = None
        
        user_progress = {
            'reaction': {
                'current_week_best': int(current_week_reaction['best_time'] * 1000) if current_week_reaction['best_time'] else None,
                'previous_week_best': int(previous_week_reaction['best_time'] * 1000) if previous_week_reaction['best_time'] else None,
                'improvement_ms': int(reaction_improvement) if reaction_improvement else None,
                'improvement_ms_abs': int(abs(reaction_improvement)) if reaction_improvement else None,
                'improvement_percent': round(reaction_improvement_percent, 1) if reaction_improvement_percent else None,
                'improvement_percent_abs': round(abs(reaction_improvement_percent), 1) if reaction_improvement_percent else None,
                'is_improved': reaction_improvement > 0 if reaction_improvement else None,
            },
            'evade': {
                'current_week_best': current_week_evade['best_score'],
                'previous_week_best': previous_week_evade['best_score'],
                'improvement_points': evade_improvement,
                'improvement_points_abs': abs(evade_improvement) if evade_improvement else None,
                'improvement_percent': round(evade_improvement_percent, 1) if evade_improvement_percent else None,
                'improvement_percent_abs': round(abs(evade_improvement_percent), 1) if evade_improvement_percent else None,
                'is_improved': evade_improvement > 0 if evade_improvement else None,
            }
        }
    
    # Reaction Test Leaderboard
    reaction_test_query = ReactionTestResult.objects.filter(is_for_leaderboard=True)
    if start_date:
        reaction_test_query = reaction_test_query.filter(timestamp__gte=start_date)
    
    reaction_test_best_scores = reaction_test_query.values('user').annotate(
        best_time=models.Min('time')
    ).order_by('best_time')

    # Get user details for the top 100
    reaction_test_top_100_user_ids = [score['user'] for score in reaction_test_best_scores[:100]]
    reaction_test_users = User.objects.in_bulk(reaction_test_top_100_user_ids)

    reaction_test_leaderboard = []
    for rank, score in enumerate(reaction_test_best_scores[:100], 1):
        user = reaction_test_users.get(score['user'])
        if user:
            # Find the ReactionTestResult with this user's best_time
            best_result = ReactionTestResult.objects.filter(user=user, is_for_leaderboard=True, time=score['best_time']).order_by('timestamp').first()
            reaction_test_leaderboard.append({
                'rank': rank,
                'user_id': user.id,
                'name': f"{user.first_name} {user.last_name}",
                'username': user.username,
                'best_time': int(score['best_time'] * 1000),
                'timestamp': best_result.timestamp if best_result else None,
            })
    
    # Reaction Test stats
    reaction_test_total_players = User.objects.filter(reactiontestresult__is_for_leaderboard=True).distinct().count()
    reaction_test_average_time_agg = reaction_test_query.aggregate(models.Avg('time'))
    reaction_test_average_time = int(reaction_test_average_time_agg['time__avg'] * 1000) if reaction_test_average_time_agg['time__avg'] else None

    # Current user's reaction test rank and best time
    reaction_test_current_user_rank = None
    reaction_test_your_best = None
    if request.user.is_authenticated:
        user_best_score = reaction_test_best_scores.filter(user=request.user).first()
        if user_best_score:
            reaction_test_your_best = int(user_best_score['best_time'] * 1000)
            # Find rank
            all_ranked_ids = [score['user'] for score in reaction_test_best_scores]
            try:
                reaction_test_current_user_rank = all_ranked_ids.index(request.user.id) + 1
            except ValueError:
                reaction_test_current_user_rank = None

    # Reorder top 3 for the podium display [Rank 2, Rank 1, Rank 3]
    reaction_test_top3_podium = reaction_test_leaderboard[:3]
    if len(reaction_test_top3_podium) == 3:
        reaction_test_top3_podium = [reaction_test_top3_podium[1], reaction_test_top3_podium[0], reaction_test_top3_podium[2]]

    # Evade & Sequence Leaderboard
    evade_sequence_query = EvadeAndSequenceResult.objects.all()
    if start_date:
        evade_sequence_query = evade_sequence_query.filter(timestamp__gte=start_date)
    
    evade_sequence_best_scores = evade_sequence_query.values('user').annotate(
        best_score=models.Max('score')
    ).order_by('-best_score')

    # Get user details for the top 100
    evade_sequence_top_100_user_ids = [score['user'] for score in evade_sequence_best_scores[:100]]
    evade_sequence_users = User.objects.in_bulk(evade_sequence_top_100_user_ids)

    evade_sequence_leaderboard = []
    for rank, score in enumerate(evade_sequence_best_scores[:100], 1):
        user = evade_sequence_users.get(score['user'])
        if user:
            # Find the EvadeAndSequenceResult with this user's best_score
            best_result = EvadeAndSequenceResult.objects.filter(user=user, score=score['best_score']).order_by('timestamp').first()
            evade_sequence_leaderboard.append({
                'rank': rank,
                'user_id': user.id,
                'name': f"{user.first_name} {user.last_name}",
                'username': user.username,
                'best_score': score['best_score'],
                'timestamp': best_result.timestamp if best_result else None,
            })
    
    # Evade & Sequence stats
    evade_sequence_total_players = User.objects.filter(evadeandsequenceresult__isnull=False).distinct().count()
    evade_sequence_average_score_agg = evade_sequence_query.aggregate(models.Avg('score'))
    evade_sequence_average_score = int(evade_sequence_average_score_agg['score__avg']) if evade_sequence_average_score_agg['score__avg'] else None

    # Current user's evade & sequence rank and best score
    evade_sequence_current_user_rank = None
    evade_sequence_your_best = None
    if request.user.is_authenticated:
        user_best_score = evade_sequence_best_scores.filter(user=request.user).first()
        if user_best_score:
            evade_sequence_your_best = user_best_score['best_score']
            # Find rank
            all_ranked_ids = [score['user'] for score in evade_sequence_best_scores]
            try:
                evade_sequence_current_user_rank = all_ranked_ids.index(request.user.id) + 1
            except ValueError:
                evade_sequence_current_user_rank = None

    # Reorder top 3 for the podium display [Rank 2, Rank 1, Rank 3]
    evade_sequence_top3_podium = evade_sequence_leaderboard[:3]
    if len(evade_sequence_top3_podium) == 3:
        evade_sequence_top3_podium = [evade_sequence_top3_podium[1], evade_sequence_top3_podium[0], evade_sequence_top3_podium[2]]

    context = {
        # Time filter
        'time_filter': time_filter,
        
        # User progress
        'user_progress': user_progress,
        
        # Reaction Test data
        'reaction_test_leaderboard': {
            'full': reaction_test_leaderboard,
            'top3': reaction_test_top3_podium,
        },
        'reaction_test_stats': {
            'current_user_rank': reaction_test_current_user_rank,
            'total_players': reaction_test_total_players,
            'average_time': reaction_test_average_time,
            'your_best': reaction_test_your_best,
        },
        
        # Evade & Sequence data
        'evade_sequence_leaderboard': {
            'full': evade_sequence_leaderboard,
            'top3': evade_sequence_top3_podium,
        },
        'evade_sequence_stats': {
            'current_user_rank': evade_sequence_current_user_rank,
            'total_players': evade_sequence_total_players,
            'average_score': evade_sequence_average_score,
            'your_best': evade_sequence_your_best,
        },
        
        'user_id': request.user.id
    }
    return render(request, 'accounts/leaderboard.html', context)

@login_required
def profile_view(request):
    user = request.user
    
    # Calculate progress data for current user
    from datetime import datetime, timedelta
    now = timezone.now()
    
    # Current week (last 7 days)
    current_week_start = now - timedelta(weeks=1)
    # Previous week (7 days before that)
    previous_week_start = now - timedelta(weeks=2)
    previous_week_end = current_week_start
    
    # Reaction Test Progress
    current_week_reaction = ReactionTestResult.objects.filter(
        user=user,
        is_for_leaderboard=True,
        timestamp__gte=current_week_start
    ).aggregate(best_time=models.Min('time'))
    
    previous_week_reaction = ReactionTestResult.objects.filter(
        user=user,
        is_for_leaderboard=True,
        timestamp__gte=previous_week_start,
        timestamp__lt=previous_week_end
    ).aggregate(best_time=models.Min('time'))
    
    if current_week_reaction['best_time'] and previous_week_reaction['best_time']:
        reaction_improvement = (previous_week_reaction['best_time'] - current_week_reaction['best_time']) * 1000  # Convert to ms
        reaction_improvement_percent = ((previous_week_reaction['best_time'] - current_week_reaction['best_time']) / previous_week_reaction['best_time']) * 100
    else:
        reaction_improvement = None
        reaction_improvement_percent = None
    
    # Evade & Sequence Progress
    current_week_evade = EvadeAndSequenceResult.objects.filter(
        user=user,
        timestamp__gte=current_week_start
    ).aggregate(best_score=models.Max('score'))
    
    previous_week_evade = EvadeAndSequenceResult.objects.filter(
        user=user,
        timestamp__gte=previous_week_start,
        timestamp__lt=previous_week_end
    ).aggregate(best_score=models.Max('score'))
    
    if current_week_evade['best_score'] and previous_week_evade['best_score']:
        evade_improvement = current_week_evade['best_score'] - previous_week_evade['best_score']
        evade_improvement_percent = ((current_week_evade['best_score'] - previous_week_evade['best_score']) / previous_week_evade['best_score']) * 100
    else:
        evade_improvement = None
        evade_improvement_percent = None
    
    user_progress = {
        'reaction': {
            'current_week_best': int(current_week_reaction['best_time'] * 1000) if current_week_reaction['best_time'] else None,
            'previous_week_best': int(previous_week_reaction['best_time'] * 1000) if previous_week_reaction['best_time'] else None,
            'improvement_ms': int(reaction_improvement) if reaction_improvement else None,
            'improvement_ms_abs': int(abs(reaction_improvement)) if reaction_improvement else None,
            'improvement_percent': round(reaction_improvement_percent, 1) if reaction_improvement_percent else None,
            'improvement_percent_abs': round(abs(reaction_improvement_percent), 1) if reaction_improvement_percent else None,
            'is_improved': reaction_improvement > 0 if reaction_improvement else None,
        },
        'evade': {
            'current_week_best': current_week_evade['best_score'],
            'previous_week_best': previous_week_evade['best_score'],
            'improvement_points': evade_improvement,
            'improvement_points_abs': abs(evade_improvement) if evade_improvement else None,
            'improvement_percent': round(evade_improvement_percent, 1) if evade_improvement_percent else None,
            'improvement_percent_abs': round(abs(evade_improvement_percent), 1) if evade_improvement_percent else None,
            'is_improved': evade_improvement > 0 if evade_improvement else None,
        }
    }
    
    # Reaction Test Results
    all_reaction_results = ReactionTestResult.objects.filter(user=user)
    ranked_reaction_results = all_reaction_results.filter(is_for_leaderboard=True)
    
    reaction_tests_completed = all_reaction_results.count()
    reaction_best_time = ranked_reaction_results.order_by('time').first().time * 1000 if ranked_reaction_results.exists() else None
    reaction_average_time = all_reaction_results.aggregate(models.Avg('time'))['time__avg']
    if reaction_average_time:
        reaction_average_time *= 1000
    
    # Get recent reaction tests for the table
    recent_reaction_tests = all_reaction_results.order_by('-timestamp')[:5]
    
    # Reaction Test chart data (last 15 tests)
    reaction_chart_data = all_reaction_results.order_by('timestamp').select_related('user')[:15]
    reaction_chart_labels = [test.timestamp.strftime("%b %d") for test in reaction_chart_data]
    reaction_chart_scores = [test.time * 1000 for test in reaction_chart_data]
    
    # Evade & Sequence Results
    all_evade_results = EvadeAndSequenceResult.objects.filter(user=user)
    
    evade_games_completed = all_evade_results.count()
    evade_best_score = all_evade_results.order_by('-score').first().score if all_evade_results.exists() else None
    evade_average_score = all_evade_results.aggregate(models.Avg('score'))['score__avg']
    
    # Get recent evade games for the table
    recent_evade_games = all_evade_results.order_by('-timestamp')[:5]
    
    # Evade & Sequence chart data (last 15 games)
    evade_chart_data = all_evade_results.order_by('timestamp').select_related('user')[:15]
    evade_chart_labels = [game.timestamp.strftime("%b %d") for game in evade_chart_data]
    evade_chart_scores = [game.score for game in evade_chart_data]
    
    # Get recent logins
    recent_logins = LoginHistory.objects.filter(user=user).order_by('-timestamp')[:5]

    context = {
        'user_progress': user_progress,
        'reaction_stats': {
            'tests_completed': reaction_tests_completed,
            'average_time': int(reaction_average_time) if reaction_average_time else None,
            'best_time': int(reaction_best_time) if reaction_best_time else None,
        },
        'evade_stats': {
            'games_completed': evade_games_completed,
            'average_score': int(evade_average_score) if evade_average_score else None,
            'best_score': evade_best_score,
        },
        'recent_reaction_tests': recent_reaction_tests,
        'recent_evade_games': recent_evade_games,
        'reaction_chart_labels': json.dumps(reaction_chart_labels),
        'reaction_chart_scores': json.dumps(reaction_chart_scores),
        'evade_chart_labels': json.dumps(evade_chart_labels),
        'evade_chart_scores': json.dumps(evade_chart_scores),
        'recent_logins': recent_logins,
    }
    return render(request, 'accounts/profile.html', context)

def is_staff(user):
    return user.is_staff

@user_passes_test(is_staff)
@login_required
def admin_dashboard_view(request):
    # Stats
    total_users = User.objects.count()
    online_users = UserOnlineStatus.objects.filter(is_online=True).count()
    admins = User.objects.filter(is_staff=True).count()
    offline_users = total_users - online_users
    
    stats = {
        'total_users': total_users,
        'active_users': online_users,
        'admins': admins,
        'banned_users': offline_users,
    }
    
    # User list with pagination
    user_list = User.objects.select_related('useronlinestatus').order_by('-date_joined')
    paginator = Paginator(user_list, 10)  # 10 users per page
    page_number = request.GET.get('page')
    try:
        users_page = paginator.page(page_number)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)

    context = {
        'stats': stats,
        'users': users_page,
    }
    return render(request, 'accounts/admin_dashboard.html', context)

@user_passes_test(is_staff)
@login_required
def edit_user_view(request, user_id):
    try:
        user_to_edit = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        # Handle form submission
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        is_staff = request.POST.get('is_staff') == 'on'
        
        # Basic validation
        if not email:
            messages.error(request, 'Email is required.')
        elif not first_name or not last_name:
            messages.error(request, 'First name and last name are required.')
        else:
            # Update user
            user_to_edit.first_name = first_name
            user_to_edit.last_name = last_name
            user_to_edit.email = email
            user_to_edit.is_active = is_active
            user_to_edit.is_staff = is_staff
            user_to_edit.save()
            
            messages.success(request, f'User {user_to_edit.username} has been updated successfully.')
            return redirect('admin_dashboard')
    
    context = {
        'user_to_edit': user_to_edit,
    }
    return render(request, 'accounts/edit_user.html', context)

@login_required
def view_profile_view(request, user_id):
    try:
        profile_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('admin_dashboard')
    
    # Get all user's game statistics
    all_reaction_results = ReactionTestResult.objects.filter(user=profile_user).order_by('-timestamp')
    all_evade_results = EvadeAndSequenceResult.objects.filter(user=profile_user).order_by('-timestamp')

    # Last 5 for quick view
    reaction_results = all_reaction_results[:5]
    evade_results = all_evade_results[:5]
    
    # Calculate statistics
    total_reaction_tests = all_reaction_results.count()
    total_evade_games = all_evade_results.count()
    
    # Best scores
    best_reaction = all_reaction_results.order_by('time').first()
    best_evade = all_evade_results.order_by('-score').first()
    
    # Average scores
    avg_reaction_time = all_reaction_results.aggregate(avg_time=Avg('time'))['avg_time']
    avg_evade_score = all_evade_results.aggregate(avg_score=Avg('score'))['avg_score']
    
    # Chart data for reaction tests (last 15 tests)
    reaction_chart_data = all_reaction_results.order_by('timestamp')[:15]
    reaction_chart_labels = [test.timestamp.strftime("%b %d") for test in reaction_chart_data]
    reaction_chart_scores = [test.time * 1000 for test in reaction_chart_data]
    
    # Chart data for evade games (last 15 games)
    evade_chart_data = all_evade_results.order_by('timestamp')[:15]
    evade_chart_labels = [game.timestamp.strftime("%b %d") for game in evade_chart_data]
    evade_chart_scores = [game.score for game in evade_chart_data]
    
    # Recent activity
    recent_logins = LoginHistory.objects.filter(user=profile_user).order_by('-timestamp')[:5]
    
    # Calculate improvement over last 7 days vs previous week
    from datetime import timedelta
    now = timezone.now()
    
    # Current week (last 7 days)
    current_week_start = now - timedelta(days=7)
    # Previous week (7 days before that)
    previous_week_start = now - timedelta(days=14)
    previous_week_end = current_week_start
    
    # Reaction Test Improvement
    current_week_reaction = ReactionTestResult.objects.filter(
        user=profile_user,
        timestamp__gte=current_week_start
    ).aggregate(avg_time=Avg('time'))
    
    previous_week_reaction = ReactionTestResult.objects.filter(
        user=profile_user,
        timestamp__gte=previous_week_start,
        timestamp__lt=previous_week_end
    ).aggregate(avg_time=Avg('time'))
    
    reaction_improvement = None
    reaction_improvement_amount = None
    if current_week_reaction['avg_time'] and previous_week_reaction['avg_time']:
        # Lower time is better for reaction test
        improvement_ms = (previous_week_reaction['avg_time'] - current_week_reaction['avg_time']) * 1000
        reaction_improvement = improvement_ms > 0
        reaction_improvement_amount = abs(improvement_ms)
    
    # Evade & Sequence Improvement
    current_week_evade = EvadeAndSequenceResult.objects.filter(
        user=profile_user,
        timestamp__gte=current_week_start
    ).aggregate(avg_score=Avg('score'))
    
    previous_week_evade = EvadeAndSequenceResult.objects.filter(
        user=profile_user,
        timestamp__gte=previous_week_start,
        timestamp__lt=previous_week_end
    ).aggregate(avg_score=Avg('score'))
    
    evade_improvement = None
    evade_improvement_amount = None
    if current_week_evade['avg_score'] and previous_week_evade['avg_score']:
        # Higher score is better for evade & sequence
        improvement_points = current_week_evade['avg_score'] - previous_week_evade['avg_score']
        evade_improvement = improvement_points > 0
        evade_improvement_amount = abs(improvement_points)
    
    context = {
        'profile_user': profile_user,
        'reaction_results': reaction_results,
        'evade_results': evade_results,
        'all_reaction_results': all_reaction_results,
        'all_evade_results': all_evade_results,
        'total_reaction_tests': total_reaction_tests,
        'total_evade_games': total_evade_games,
        'best_reaction': best_reaction,
        'best_evade': best_evade,
        'avg_reaction_time': avg_reaction_time,
        'avg_evade_score': avg_evade_score,
        'recent_logins': recent_logins,
        'reaction_chart_labels': json.dumps(reaction_chart_labels),
        'reaction_chart_scores': json.dumps(reaction_chart_scores),
        'evade_chart_labels': json.dumps(evade_chart_labels),
        'evade_chart_scores': json.dumps(evade_chart_scores),
        'reaction_improvement': reaction_improvement,
        'reaction_improvement_amount': reaction_improvement_amount,
        'evade_improvement': evade_improvement,
        'evade_improvement_amount': evade_improvement_amount,
        'current_week_reaction_avg': current_week_reaction['avg_time'],
        'previous_week_reaction_avg': previous_week_reaction['avg_time'],
        'current_week_evade_avg': current_week_evade['avg_score'],
        'previous_week_evade_avg': previous_week_evade['avg_score'],
    }
    return render(request, 'accounts/view_profile.html', context)

@login_required
def reaction_test_view(request):
    # Check how many ranked attempts the user has (excluding expired ones)
    from datetime import timedelta
    cutoff_time = timezone.now() - timedelta(hours=24)
    
    recent_ranked_attempts = ReactionTestResult.objects.filter(
        user=request.user, 
        is_for_leaderboard=True,
        ranked_attempt_timestamp__gte=cutoff_time
    ).order_by('ranked_attempt_timestamp')
    ranked_attempts_count = recent_ranked_attempts.count()

    next_ranked_attempt_time = None
    if ranked_attempts_count >= 3:
        # The earliest of the last 3 attempts will expire first
        third_earliest = recent_ranked_attempts[0]
        next_ranked_attempt_time = third_earliest.ranked_attempt_timestamp + timedelta(hours=24)

    context = {
        'ranked_attempts_count': ranked_attempts_count,
        'next_ranked_attempt_time': next_ranked_attempt_time,
    }
    return render(request, 'accounts/reaction_test.html', context)

@login_required
def save_score_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            time = data.get('time')
            scores = data.get('scores', [])

            if time is not None:
                # Check how many ranked attempts the user has (excluding expired ones)
                from datetime import timedelta
                cutoff_time = timezone.now() - timedelta(hours=24)
                
                ranked_attempts_count = ReactionTestResult.objects.filter(
                    user=request.user, 
                    is_for_leaderboard=True,
                    ranked_attempt_timestamp__gte=cutoff_time
                ).count()

                is_ranked = ranked_attempts_count < 3

                time_seconds = float(time) / 1000.0
                ReactionTestResult.objects.create(
                    user=request.user, 
                    time=time_seconds,
                    is_for_leaderboard=is_ranked,
                    ranked_attempt_timestamp=timezone.now() if is_ranked else None
                )

                # Store session data for the result page
                request.session['last_reaction_test_data'] = {
                    'scores': scores,
                    'average_score': time,
                }
                return JsonResponse({'status': 'success', 'is_ranked': is_ranked, 'attempts_left': max(0, 2 - ranked_attempts_count)})
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

def reaction_test_result_view(request):
    session_data = request.session.get('last_reaction_test_data')
    if not session_data:
        return redirect('dashboard')

    # Clear the session data after reading it
    del request.session['last_reaction_test_data']

    user = request.user
    user_results = ReactionTestResult.objects.filter(user=user)
    best_time = user_results.order_by('time').first().time * 1000 if user_results.exists() else None
    
    # Calculate global rank
    global_rank = None
    if best_time is not None:
        all_best_times = ReactionTestResult.objects.values('user').annotate(min_time=models.Min('time')).order_by('min_time')
        user_ranks = {item['user']: rank + 1 for rank, item in enumerate(all_best_times)}
        global_rank = user_ranks.get(user.id)

    user_stats = {
        'best_time': best_time,
        'global_rank': global_rank,
    }

    # Calculate progress bar width (1000 ms = 100%, 2000 ms = 50%, min 5%)
    avg = float(session_data['average_score']) if session_data.get('average_score') else 0
    progress_width = max(5, min(100, int(1000 / avg * 100))) if avg > 0 else 100

    # Get performance comment
    if avg <= 150:
        performance_comment = "Absolutely lightning fast! A true ReactionTest master!"
    elif avg <= 250:
        performance_comment = "Incredible speed! You're in the top percentile."
    elif avg <= 350:
        performance_comment = "Great job! Your reflexes are sharp."
    elif avg <= 500:
        performance_comment = "Solid effort. Keep practicing to get even faster!"
    else:
        performance_comment = "Keep at it! Every attempt makes you quicker."

    context = {
        'session_data': session_data,
        'user_stats': user_stats,
        'progress_width': progress_width,
        'performance_comment': performance_comment,
    }
    return render(request, 'accounts/reaction_test_result.html', context)

# --- Evade & Sequence Game Views ---

@login_required
def evade_and_sequence_view(request):
    # Logic to be added
    return render(request, 'accounts/evade_and_sequence.html')

@login_required
def evade_and_sequence_warning_view(request):
    """Show the warning/preparation page for Evade & Sequence game"""
    return render(request, 'accounts/evade_and_sequence_warning.html')

@login_required
def save_evade_and_sequence_score_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')
            misses = data.get('misses')

            if score is not None and misses is not None:
                result = EvadeAndSequenceResult.objects.create(
                    user=request.user, 
                    score=int(score),
                    misses=int(misses)
                )
                return JsonResponse({'status': 'success', 'result_id': result.id})
            else:
                return JsonResponse({'status': 'error', 'message': 'Missing score or misses data'}, status=400)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def evade_and_sequence_result_view(request, result_id):
    try:
        result = EvadeAndSequenceResult.objects.get(id=result_id, user=request.user)
    except EvadeAndSequenceResult.DoesNotExist:
        return redirect('dashboard')
        
    context = {
        'result': result
    }
    return render(request, 'accounts/evade_and_sequence_result.html', context)

@login_required
def manage_devices_view(request):
    """View to manage trusted devices"""
    if request.method == 'POST':
        device_id = request.POST.get('remove_device')
        if device_id:
            try:
                device = DeviceFingerprint.objects.get(
                    id=device_id,
                    user=request.user
                )
                device.delete()
                messages.success(request, 'Device removed successfully!')
            except DeviceFingerprint.DoesNotExist:
                messages.error(request, 'Device not found.')
    
    # Get all trusted devices for the user
    trusted_devices = DeviceFingerprint.objects.filter(
        user=request.user,
        is_trusted=True
    ).order_by('-last_used')
    
    context = {
        'trusted_devices': trusted_devices
    }
    return render(request, 'accounts/manage_devices.html', context)

@user_passes_test(is_staff)
@login_required
def delete_user_view(request, user_id):
    """Delete a user account with proper safety checks and confirmation"""
    try:
        user_to_delete = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('admin_dashboard')
    
    # Prevent admin from deleting themselves
    if user_to_delete == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin_dashboard')
    
    # Prevent deletion of other admin accounts
    if user_to_delete.is_staff and not request.user.is_superuser:
        messages.error(request, 'Only superusers can delete admin accounts.')
        return redirect('admin_dashboard')
    
    # Prevent deletion of the last admin account
    if user_to_delete.is_staff:
        admin_count = User.objects.filter(is_staff=True).count()
        if admin_count <= 1:
            messages.error(request, 'Cannot delete the last administrator account.')
            return redirect('admin_dashboard')
    
    if request.method == 'POST':
        # Check for confirmation
        confirm_delete = request.POST.get('confirm_delete')
        if confirm_delete == 'yes':
            # Log the deletion for audit purposes
            print(f"ADMIN AUDIT: User {request.user.username} (ID: {request.user.id}) deleted user {user_to_delete.username} (ID: {user_to_delete.id}) at {timezone.now()}")
            
            # Store user info before deletion for logging
            deleted_username = user_to_delete.username
            deleted_email = user_to_delete.email
            
            # Delete the user (this will cascade delete all related data due to CASCADE relationships)
            user_to_delete.delete()
            
            messages.success(request, f'User "{deleted_username}" has been permanently deleted.')
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'User deletion cancelled.')
            return redirect('admin_dashboard')
    
    # GET request - show confirmation page
    context = {
        'user_to_delete': user_to_delete,
        'related_data': {
            'reaction_results': ReactionTestResult.objects.filter(user=user_to_delete).count(),
            'evade_results': EvadeAndSequenceResult.objects.filter(user=user_to_delete).count(),
            'login_history': LoginHistory.objects.filter(user=user_to_delete).count(),
            'device_fingerprints': DeviceFingerprint.objects.filter(user=user_to_delete).count(),
        }
    }
    
    return render(request, 'accounts/delete_user_confirmation.html', context)

@login_required
def evade_and_sequence_instructions_view(request):
    """Show the instructions page for Evade & Sequence game"""
    return render(request, 'accounts/evade_and_sequence_instructions.html')

@user_passes_test(is_staff)
@login_required
def get_online_status_api(request):
    """API endpoint to get real-time online status of all users"""
    if request.method == 'GET':
        # Get all users with their online status
        users_status = []
        users = User.objects.select_related('useronlinestatus').all()
        
        for user in users:
            try:
                online_status = user.useronlinestatus
                users_status.append({
                    'user_id': user.id,
                    'username': user.username,
                    'is_online': online_status.is_online,
                    'last_seen': online_status.last_seen.isoformat() if online_status.last_seen else None,
                })
            except UserOnlineStatus.DoesNotExist:
                # User doesn't have online status record yet
                users_status.append({
                    'user_id': user.id,
                    'username': user.username,
                    'is_online': False,
                    'last_seen': None,
                })
        
        response_data = {
            'status': 'success',
            'users': users_status,
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(response_data)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@user_passes_test(is_staff)
@login_required
def debug_online_status_view(request):
    """Debug endpoint to check online status system"""
    if request.method == 'GET':
        # Get current user's status
        try:
            current_user_status = UserOnlineStatus.objects.get(user=request.user)
            current_status = {
                'user_id': request.user.id,
                'username': request.user.username,
                'is_online': current_user_status.is_online,
                'last_seen': current_user_status.last_seen.isoformat() if current_user_status.last_seen else None,
                'session_key': current_user_status.session_key,
            }
        except UserOnlineStatus.DoesNotExist:
            current_status = {
                'user_id': request.user.id,
                'username': request.user.username,
                'is_online': False,
                'last_seen': None,
                'session_key': None,
                'error': 'No status record found'
            }
        
        # Get all users status
        all_users_status = []
        users = User.objects.select_related('useronlinestatus').all()
        
        for user in users:
            try:
                online_status = user.useronlinestatus
                all_users_status.append({
                    'user_id': user.id,
                    'username': user.username,
                    'is_online': online_status.is_online,
                    'last_seen': online_status.last_seen.isoformat() if online_status.last_seen else None,
                })
            except UserOnlineStatus.DoesNotExist:
                all_users_status.append({
                    'user_id': user.id,
                    'username': user.username,
                    'is_online': False,
                    'last_seen': None,
                    'error': 'No status record'
                })
        
        # Cache status
        cache_status = {
            'cache_key_exists': cache.get('all_users_online_status') is not None,
            'user_cache_key': f'user_online_{request.user.id}',
            'user_cache_exists': cache.get(f'user_online_{request.user.id}') is not None,
        }
        
        debug_data = {
            'status': 'success',
            'current_user': current_status,
            'all_users': all_users_status,
            'cache_status': cache_status,
            'timestamp': timezone.now().isoformat(),
            'total_users': len(all_users_status),
            'online_users': len([u for u in all_users_status if u['is_online']]),
            'offline_users': len([u for u in all_users_status if not u['is_online']]),
        }
        
        return JsonResponse(debug_data)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def rank_status_view(request):
    # Get the user's most recent ranked attempt
    last_ranked = ReactionTestResult.objects.filter(
        user=request.user,
        is_for_leaderboard=True,
        ranked_attempt_timestamp__isnull=False
    ).order_by('-ranked_attempt_timestamp').first()

    can_play_ranked = True
    wait_hours = wait_minutes = 0
    time_until_next_ranked = None

    if last_ranked:
        time_since_last = timezone.now() - last_ranked.ranked_attempt_timestamp
        if time_since_last < timedelta(hours=24):
            can_play_ranked = False
            time_until_next_ranked = timedelta(hours=24) - time_since_last
            wait_hours = time_until_next_ranked.seconds // 3600
            wait_minutes = (time_until_next_ranked.seconds % 3600) // 60

    context = {
        'can_play_ranked': can_play_ranked,
        'wait_hours': wait_hours,
        'wait_minutes': wait_minutes,
        'time_until_next_ranked': time_until_next_ranked,
    }
    return render(request, 'accounts/rank_status.html', context)
