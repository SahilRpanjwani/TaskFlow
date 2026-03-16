# core/views.py

"""
Django Views for Task Management System

This file contains all the views for a role-based task management system with:
- Three user roles: Admin, Boss, Employee
- Task rooms for organizing work
- Task assignment and submission workflows
- Membership management for rooms
"""

from decimal import Decimal
from datetime import date
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .forms import TaskRoomForm, UserRegisterForm, TaskForm, SubmissionForm
from .models import TaskRoom, Profile, Membership, Task, Submission


# ============================================================================
# UTILITY FUNCTIONS - Role and Permission Checking
# ============================================================================

def is_admin(user):
    """
    Check if user has admin role.
    Used as decorator test function for admin-only views.

    Args:
        user: Django User object

    Returns:
        bool: True if user is authenticated and has admin role
    """
    return user.is_authenticated and user.profile.role == 'admin'


def is_boss(user):
    """
    Check if user has boss role.
    Bosses can create rooms and assign tasks.

    Args:
        user: Django User object

    Returns:
        bool: True if user is authenticated and has boss role
    """
    return user.is_authenticated and user.profile.role == 'boss'


def is_admin_or_boss(user):
    """
    Check if user has admin or boss role.
    Used for views that allow both admins and bosses access.

    Args:
        user: Django User object

    Returns:
        bool: True if user has admin or boss role
    """
    return user.is_authenticated and user.profile.role in ['admin', 'boss']


def is_employee(user):
    """
    Check if user has employee role.
    Employees receive and complete tasks.

    Args:
        user: Django User object

    Returns:
        bool: True if user is authenticated and has employee role
    """
    return user.is_authenticated and user.profile.role == 'employee'


def has_room_access(user, room):
    """
    Check if user has access to a specific room.
    This is a comprehensive permission check for room access.

    Access rules:
    - Admin: Access to all rooms
    - Room owner: Access to their own room
    - Accepted members: Access to rooms they've joined

    Args:
        user: Django User object
        room: TaskRoom object

    Returns:
        bool: True if user can access the room
    """
    if not user.is_authenticated:
        return False

    # Admin has access to all rooms
    if user.profile.role == 'admin':
        return True

    # Room owner (creator) has access
    if room.created_by == user:
        return True

    # Check if user is an accepted member of the room
    return Membership.objects.filter(
        user=user,
        task_room=room,
        status='accepted'
    ).exists()


def can_manage_room(user, room):
    """
    Check if user can manage (edit/delete) a room.
    More restrictive than room access - only owners and admins.

    Args:
        user: Django User object
        room: TaskRoom object

    Returns:
        bool: True if user can manage the room
    """
    if not user.is_authenticated:
        return False

    # Admin can manage all rooms
    if user.profile.role == 'admin':
        return True

    # Room owner can manage their room
    return room.created_by == user


def can_assign_tasks(user):
    """
    Check if user can assign tasks to others.
    Only admins and bosses can assign tasks.

    Args:
        user: Django User object

    Returns:
        bool: True if user can assign tasks
    """
    return user.is_authenticated and user.profile.role in ['admin', 'boss']


def can_review_submissions(user):
    """
    Check if user can review task submissions.
    Only admins and bosses can review and score submissions.

    Args:
        user: Django User object

    Returns:
        bool: True if user can review submissions
    """
    return user.is_authenticated and user.profile.role in ['admin', 'boss']


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

def register_view(request):
    """
    Handle user registration with role assignment.
    Users can register with different roles during signup.

    POST: Process registration form and create user with profile
    GET: Display registration form
    """
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # Create user but don't save to DB yet (commit=False)
            user = form.save(commit=False)
            # Set password properly (hashed)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Set the user's role in their profile
            # Profile is created via Django signals when user is created
            user.profile.role = form.cleaned_data['role']
            user.profile.save()

            return redirect('login')
    else:
        form = UserRegisterForm()

    return render(request, 'core/register.html', {'form': form})


def login_view(request):
    """
    Handle user login with role-based redirection.
    Different user roles are redirected to appropriate dashboards.

    Redirection logic:
    - Admin -> Admin dashboard
    - Boss -> Room list (to manage their rooms)
    - Employee -> Task list (to see assigned tasks)
    """
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Role-based redirection after successful login
            if hasattr(user, "profile") and user.profile.role == "admin":
                return redirect("admin_dashboard")
            elif user.profile.role == "boss":
                return redirect("room_list")
            elif user.profile.role == "employee":
                return redirect("task_list")
            else:
                return redirect("home")  # Fallback for undefined roles
    else:
        form = AuthenticationForm()

    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    """
    Handle user logout and redirect to login page.
    Simple logout functionality.
    """
    logout(request)
    return redirect('login')


# ============================================================================
# DASHBOARD & HOME VIEWS
# ============================================================================

@login_required
def home(request):
    """
    Display user dashboard with statistics.
    This is the main dashboard showing role-specific information.

    Dashboard shows:
    - Role-specific statistics (rooms created/joined, tasks assigned/completed)
    - Recent tasks
    - Pending items requiring attention
    """
    profile = request.user.profile
    today = date.today()

    # Admin users are redirected to their specialized dashboard
    if profile.role == 'admin':
        return redirect('admin_dashboard')

    # Role-specific data collection
    if profile.role == 'boss':
        # Bosses see statistics about rooms they created
        rooms_count = TaskRoom.objects.filter(created_by=request.user).count()
        rooms_label = 'rooms_created'

        # Tasks in rooms created by this boss
        tasks_base_query = Task.objects.filter(task_room__created_by=request.user)

        # Submissions awaiting review in their rooms
        pending_submissions = Submission.objects.filter(
            task__task_room__created_by=request.user,
            score__isnull=True  # score__isnull=True means submission hasn't been reviewed
        ).count()

    else:  # employee role
        # Employees see statistics about rooms they've joined
        rooms_count = Membership.objects.filter(user=request.user).count()
        rooms_label = 'rooms_joined'

        # Tasks assigned specifically to this employee
        tasks_base_query = Task.objects.filter(assigned_to=request.user)
        pending_submissions = 0  # Employees don't review submissions

    # Task statistics calculation
    total_tasks = tasks_base_query.count()
    pending_tasks = tasks_base_query.filter(status='pending').count()
    completed_tasks = tasks_base_query.filter(status='completed').count()

    # Overdue tasks: deadline passed but not completed
    overdue_tasks = tasks_base_query.filter(
        deadline__lt=today
    ).exclude(status='completed').count()

    # Pending tasks that are not overdue
    pending_not_overdue = tasks_base_query.filter(
        status='pending',
        deadline__gte=today
    ).count()

    # Recent tasks for quick overview
    recent_tasks = tasks_base_query.select_related(
        'assigned_to', 'task_room'
    ).order_by('-created_at')[:5]

    # Activity score calculation (role-specific)
    if profile.role == 'boss':
        # For bosses: percentage of completed tasks in their rooms
        activity_score = round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0
    else:
        # For employees: try to use average submission score first
        reviewed_submissions = Submission.objects.filter(
            submitted_by=request.user,
            score__isnull=False  # Has been reviewed and scored
        )

        if reviewed_submissions.exists():
            # Use average score from reviewed submissions
            activity_score = reviewed_submissions.aggregate(avg_score=Avg('score'))['avg_score']
            activity_score = round(activity_score, 1) if activity_score else 0
        else:
            # Fallback to completion percentage if no scored submissions
            activity_score = round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0

    return render(request, 'core/home.html', {
        'profile': profile,
        'rooms_count': rooms_count,
        'rooms_label': rooms_label,
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'pending_not_overdue': pending_not_overdue,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'recent_tasks': recent_tasks,
        'activity_score': activity_score,
        'pending_submissions': pending_submissions,
    })


# ============================================================================
# ADMIN-SPECIFIC VIEWS
# ============================================================================

@login_required
@user_passes_test(is_admin)  # Decorator ensures only admins can access
def admin_dashboard(request):
    """
    Admin dashboard with system-wide statistics.
    Provides comprehensive overview of the entire system.

    Displays:
    - Total counts (users, rooms, tasks, submissions)
    - Role breakdown of users
    - Recent activity across the system
    - Task and submission status breakdowns
    """
    # System-wide statistics
    total_users = User.objects.count()
    total_rooms = TaskRoom.objects.count()
    total_tasks = Task.objects.count()
    total_submissions = Submission.objects.count()

    # User role breakdown
    admin_count = Profile.objects.filter(role='admin').count()
    boss_count = Profile.objects.filter(role='boss').count()
    employee_count = Profile.objects.filter(role='employee').count()

    # Recent activity for monitoring
    # select_related() reduces database queries by joining related tables
    recent_users = User.objects.select_related('profile').order_by('-date_joined')[:10]
    recent_rooms = TaskRoom.objects.select_related('created_by').order_by('-created_at')[:10]
    recent_tasks = Task.objects.select_related(
        'assigned_to', 'task_room'
    ).order_by('-created_at')[:10]

    # Task status breakdown for monitoring
    pending_tasks = Task.objects.filter(status='pending').count()
    completed_tasks = Task.objects.filter(status='completed').count()

    # Overdue tasks calculation
    overdue_tasks = Task.objects.filter(
        deadline__lt=date.today()
    ).exclude(status='completed').count()

    # Submission review status
    pending_submissions = Submission.objects.filter(score__isnull=True).count()
    reviewed_submissions = Submission.objects.exclude(score__isnull=True).count()

    context = {
        'total_users': total_users,
        'total_rooms': total_rooms,
        'total_tasks': total_tasks,
        'total_submissions': total_submissions,
        'admin_count': admin_count,
        'boss_count': boss_count,
        'employee_count': employee_count,
        'recent_users': recent_users,
        'recent_rooms': recent_rooms,
        'recent_tasks': recent_tasks,
        'pending_tasks': pending_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'pending_submissions': pending_submissions,
        'reviewed_submissions': reviewed_submissions,
    }

    return render(request, 'core/admin_dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def manage_users(request):
    """
    Admin view to manage all users and their roles.
    Provides search and filtering capabilities for user management.

    Features:
    - Search by username, email, or name
    - Filter by role
    - Display user information and roles
    """
    # Get search and filter parameters from GET request
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', 'all')

    # Start with all users, including their profiles
    users = User.objects.select_related('profile').all()

    # Apply search filter if provided
    if search_query:
        # Q objects allow complex queries with OR conditions
        users = users.filter(
            Q(username__icontains=search_query) |  # Case-insensitive contains
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    # Apply role filter if not 'all'
    if role_filter != 'all':
        users = users.filter(profile__role=role_filter)

    # Order by most recent users first
    users = users.order_by('-date_joined')

    return render(request, 'core/manage_users.html', {
        'users': users,
        'search_query': search_query,
        'role_filter': role_filter,
    })


@login_required
@user_passes_test(is_admin)
def change_user_role(request, user_id):
    """
    Admin can change any user's role.
    Handles role changes with validation and success messaging.

    Args:
        user_id: ID of the user whose role is being changed
    """
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        new_role = request.POST.get('role')

        # Validate the new role
        if new_role in ['admin', 'boss', 'employee']:
            old_role = user.profile.role
            user.profile.role = new_role
            user.profile.save()

            messages.success(
                request,
                f"Role changed for {user.username} from {old_role} to {new_role}"
            )
        else:
            messages.error(request, 'Invalid role selected')

    return redirect('manage_users')


@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    """
    Admin can delete users (except themselves).
    Includes confirmation step to prevent accidental deletions.

    Args:
        user_id: ID of the user to be deleted
    """
    user_to_delete = get_object_or_404(User, id=user_id)

    # Prevent admin from deleting their own account
    if user_to_delete == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('manage_users')

    if request.method == 'POST':
        # Store username before deletion for success message
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f"User '{username}' has been deleted.")
        return redirect('manage_users')

    # Show confirmation page on GET request
    return render(request, 'core/confirm_delete_user.html', {
        'user_to_delete': user_to_delete
    })


@login_required
@user_passes_test(is_admin)
def system_overview(request):
    """
    Admin view for comprehensive system overview.
    Advanced analytics and monitoring for system administrators.

    Displays:
    - Room statistics (public vs private)
    - Most active rooms and productive users
    - Pending reviews requiring attention
    - System performance metrics
    """
    # Room visibility statistics
    public_rooms = TaskRoom.objects.filter(is_public=True).count()
    private_rooms = TaskRoom.objects.filter(is_public=False).count()

    # Most active rooms analysis
    # annotate() adds calculated fields to each object
    active_rooms = TaskRoom.objects.annotate(
        task_count=Count('task', distinct=True),  # Count unique tasks
        member_count=Count('membership__user', distinct=True)  # Count unique members
    ).order_by('-task_count')[:10]  # Top 10 by task count

    # Most productive employees analysis
    productive_employees = User.objects.filter(
        profile__role='employee'
    ).annotate(
        # Count completed tasks assigned to this employee
        completed_tasks=Count(
            'task',
            filter=Q(task__status='completed'),
            distinct=True
        )
    ).order_by('-completed_tasks')[:10]

    # Most productive bosses analysis
    productive_bosses = User.objects.filter(
        profile__role='boss'
    ).annotate(
        rooms_created=Count('taskroom', distinct=True),
        # Count tasks in rooms they created
        tasks_assigned=Count('taskroom__task', distinct=True)
    ).order_by('-tasks_assigned')[:10]

    # Recent submissions needing review (admin priority)
    pending_reviews = Submission.objects.filter(
        score__isnull=True  # Not yet reviewed
    ).select_related(
        'task', 'submitted_by', 'task__task_room'
    ).order_by('-submitted_at')[:20]

    # System completion metrics
    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(status='completed').count()
    reviewed_submissions = Submission.objects.filter(score__isnull=False).count()

    # Overdue tasks calculation
    # Using timezone.now() instead of date.today() for better datetime handling
    overdue_tasks = Task.objects.filter(
        deadline__lt=timezone.now(),  # deadline field compared to current datetime
        status__in=['pending', 'in_progress']  # Only count non-completed tasks
    ).count()

    return render(request, 'core/system_overview.html', {
        'public_rooms': public_rooms,
        'private_rooms': private_rooms,
        'active_rooms': active_rooms,
        'productive_employees': productive_employees,
        'productive_bosses': productive_bosses,
        'pending_reviews': pending_reviews,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'reviewed_submissions': reviewed_submissions,
        'overdue_tasks': overdue_tasks,
    })


# ============================================================================
# ROOM MANAGEMENT VIEWS
# ============================================================================

@login_required
@user_passes_test(is_admin_or_boss)  # Only admins and bosses can create rooms
def create_room(request):
    """
    Create a new task room.
    Rooms can be public (anyone can join) or private (invite-only via room code).

    POST: Process room creation form
    GET: Display room creation form

    After creation:
    - Creator automatically becomes a member
    - Private rooms show the room code for sharing
    - Public rooms redirect to room list
    """
    if request.method == 'POST':
        form = TaskRoomForm(request.POST)
        if form.is_valid():
            # Create room but don't save yet
            task_room = form.save(commit=False)
            task_room.created_by = request.user

            # Handle privacy setting (checkbox logic)
            task_room.is_public = not (request.POST.get('is_private') == 'on')
            task_room.save()

            # Automatically create membership for room creator
            # Role depends on user's system role
            creator_role = 'boss' if request.user.profile.role == 'boss' else 'admin'
            Membership.objects.create(
                user=request.user,
                task_room=task_room,
                role=creator_role
            )

            messages.success(request, f"Room '{task_room.name}' created successfully!")

            # For private rooms, show the room code for sharing
            if not task_room.is_public:
                return render(request, 'core/create_room_success.html', {
                    'room_code': task_room.room_code
                })
            return redirect('room_list')
    else:
        form = TaskRoomForm()

    return render(request, 'core/create_room.html', {'form': form})


@login_required
def room_list(request):
    """
    Display list of rooms accessible to the user.
    Different roles see different room sets with role-appropriate statistics.

    Room visibility:
    - Admin: All rooms in the system
    - Boss: Only rooms they created
    - Employee: Only rooms they are members of
    """
    profile = request.user.profile

    if profile.role == 'admin':
        # Admin sees all rooms with comprehensive statistics
        rooms = TaskRoom.objects.all().annotate(
            total_tasks=Count('task'),
            pending_tasks=Count('task', filter=Q(task__status='pending')),
            completed_tasks=Count('task', filter=Q(task__status='completed')),
            member_count=Count('membership', filter=Q(membership__status='accepted'))
        ).order_by('-created_at')

    elif profile.role == 'boss':
        # Boss sees only rooms they created with task statistics
        rooms = TaskRoom.objects.filter(created_by=request.user).annotate(
            total_tasks=Count('task'),
            pending_tasks=Count('task', filter=Q(task__status='pending')),
            completed_tasks=Count('task', filter=Q(task__status='completed'))
        )

    else:  # employee
        # Employee sees rooms they are members of with their personal task stats
        rooms = TaskRoom.objects.filter(membership__user=request.user).annotate(
            total_tasks=Count('task'),
            # Personal task statistics for this employee in each room
            my_pending_tasks=Count('task', filter=Q(
                task__assigned_to=request.user,
                task__status='pending'
            )),
            my_completed_tasks=Count('task', filter=Q(
                task__assigned_to=request.user,
                task__status='completed'
            ))
        )

    return render(request, 'core/room_list.html', {
        'rooms': rooms,
        'profile': profile
    })


@login_required
def room_detail(request, room_id):
    """
    Display detailed information about a specific room.
    Comprehensive room overview with members, tasks, and statistics.

    Shows:
    - Room information and statistics
    - Member list (accepted and pending)
    - Task list for the room
    - Submission statistics
    - Management options (if user has permissions)
    """
    room = get_object_or_404(TaskRoom, id=room_id)
    profile = request.user.profile

    # Permission check using utility function
    if not has_room_access(request.user, room):
        return HttpResponseForbidden("You do not have access to this room.")

    # Room member data
    accepted_members = Membership.objects.filter(
        task_room=room,
        status='accepted'
    ).select_related('user')

    pending_members = Membership.objects.filter(
        task_room=room,
        status='pending'
    ).select_related('user')

    all_members = Membership.objects.filter(task_room=room)

    # Room task data
    tasks = Task.objects.filter(task_room=room).order_by('-deadline')

    # Submission data for this room
    # Double underscore notation traverses relationships
    submissions = Submission.objects.filter(
        task__task_room=room  # task (FK) -> task_room field
    ).select_related('task', 'submitted_by')

    pending_submissions = submissions.filter(score__isnull=True)
    reviewed_submissions = submissions.exclude(score__isnull=True)

    # Room completion metrics
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()

    # Calculate completion rate as percentage
    room_completion_rate = round(
        (completed_tasks / total_tasks) * 100, 1
    ) if total_tasks > 0 else 0

    # Permission flags for template logic
    is_owner = room.created_by == request.user
    is_admin = profile.role == 'admin'
    can_manage = can_manage_room(request.user, room)

    return render(request, 'core/room_detail.html', {
        'room': room,
        'members': all_members,
        'accepted_members': accepted_members,
        'pending_members': pending_members,
        'tasks': tasks,
        'pending_submissions': pending_submissions,
        'reviewed_submissions': reviewed_submissions,
        'is_owner': is_owner,
        'is_admin': is_admin,
        'can_manage': can_manage,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'room_completion_rate': room_completion_rate,
    })


@login_required
def join_room(request):
    """
    Allow employees to join rooms by selecting or by room code.
    Two ways to join:
    1. Select from available public rooms
    2. Enter private room code

    Join behavior:
    - Public rooms: Immediate acceptance
    - Private rooms: Pending approval from room owner/admin
    """
    # Only employees can join rooms
    if request.user.profile.role not in ['employee']:
        return HttpResponseForbidden("Only employees can join rooms.")

    if request.method == 'POST':
        room_code = request.POST.get('room_code')
        room_id = request.POST.get('room_id')

        # Joining by room code (private rooms)
        if room_code:
            try:
                task_room = get_object_or_404(TaskRoom, room_code=room_code)

                # Check if already a member
                if not Membership.objects.filter(
                        user=request.user,
                        task_room=task_room
                ).exists():
                    # Create pending membership for approval
                    Membership.objects.create(
                        user=request.user,
                        task_room=task_room,
                        role='employee',
                        status='pending'
                    )
                    messages.success(
                        request,
                        f"Your application to join '{task_room.name}' has been sent!"
                    )
                else:
                    messages.info(
                        request,
                        f"You have already applied or are a member of '{task_room.name}'."
                    )
                return redirect('room_list')

            except TaskRoom.DoesNotExist:
                messages.error(request, "Invalid room code.")
                return redirect('join_room')

        # Joining by room selection (public/private rooms)
        elif room_id:
            try:
                room = get_object_or_404(TaskRoom, id=room_id)

                # Check if already a member
                existing_membership = Membership.objects.filter(
                    user=request.user,
                    task_room=room
                ).exists()

                if not existing_membership:
                    if room.is_public:
                        # Public rooms: immediate acceptance
                        Membership.objects.create(
                            user=request.user,
                            task_room=room,
                            role='employee',
                            status='accepted'
                        )
                        messages.success(request, f"Successfully joined '{room.name}'!")
                    else:
                        # Private rooms: pending approval
                        Membership.objects.create(
                            user=request.user,
                            task_room=room,
                            role='employee',
                            status='pending'
                        )
                        messages.success(
                            request,
                            f"Your application to join '{room.name}' has been sent!"
                        )
                else:
                    messages.info(request, f"You are already a member of '{room.name}'.")

                return redirect('join_room')

            except TaskRoom.DoesNotExist:
                messages.error(request, "The selected room does not exist.")
                return redirect('join_room')

    # GET request: Show available public rooms
    # Exclude rooms user is already a member of
    joined_rooms_ids = Membership.objects.filter(
        user=request.user
    ).values_list('task_room_id', flat=True)

    public_rooms = TaskRoom.objects.filter(
        is_public=True
    ).exclude(id__in=joined_rooms_ids).annotate(
        member_count=Count('membership'),
        task_count=Count('task')
    )

    return render(request, 'core/join_room.html', {
        'public_rooms': public_rooms
    })


@login_required
def delete_room(request, room_id):
    """
    Allow authorized users to delete a room.
    Includes confirmation step to prevent accidental deletion.

    Only room owners and admins can delete rooms.
    Deleting a room cascades to delete all related tasks and submissions.
    """
    room = get_object_or_404(TaskRoom, id=room_id)

    # Permission check using utility function
    if not can_manage_room(request.user, room):
        return HttpResponseForbidden("You are not authorized to delete this room.")

    if request.method == 'POST':
        # Store room name before deletion for success message
        room_name = room.name
        room.delete()  # Cascading delete handles related objects
        messages.success(request, f"Room '{room_name}' was successfully deleted.")
        return redirect('room_list')

    # Show confirmation page on GET request
    return render(request, 'core/confirm_delete_room.html', {'room': room})


@login_required
def edit_room(request, room_id):
    """
    Edit room details.
    Only room owners and admins can edit room information.

    Args:
        room_id: ID of the room to be edited
    """
    room = get_object_or_404(TaskRoom, id=room_id)

    # Permission check using utility function
    if not can_manage_room(request.user, room):
        return HttpResponseForbidden("You are not authorized to edit this room.")

    if request.method == 'POST':
        # Use existing room instance to update fields
        form = TaskRoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, "Room details updated successfully!")
            return redirect('room_detail', room_id=room.id)
    else:
        # Pre-populate form with existing room data
        form = TaskRoomForm(instance=room)

    return render(request, 'core/edit_room.html', {
        'form': form,
        'room': room
    })


@login_required
def remove_member(request, room_id):
    """
    Remove a member from a room.
    Only room owners and admins can remove members.
    Users cannot remove themselves from rooms.

    Args:
        room_id: ID of the room
        member_id: Passed via POST data
    """
    if request.method == 'POST':
        room = get_object_or_404(TaskRoom, id=room_id)

        # Permission check using utility function
        if not can_manage_room(request.user, room):
            return HttpResponseForbidden("You are not authorized to manage this room.")

        member_id = request.POST.get('member_id')
        member_to_remove = get_object_or_404(Membership, id=member_id, task_room=room)

        # Prevent users from removing themselves
        if member_to_remove.user == request.user:
            messages.error(request, "You cannot remove yourself from the room.")
        else:
            username = member_to_remove.user.username
            member_to_remove.delete()
            messages.success(request, f"Successfully removed {username} from the room.")

    return redirect('room_detail', room_id=room_id)


@login_required
def accept_member(request, room_id, membership_id):
    """
    Allow authorized users to accept a pending membership request.
    Changes membership status from 'pending' to 'accepted'.

    Args:
        room_id: ID of the room
        membership_id: ID of the membership to accept
    """
    room = get_object_or_404(TaskRoom, id=room_id)

    # Permission check using utility function
    if not can_manage_room(request.user, room):
        return HttpResponseForbidden("You are not authorized to manage this room.")

    membership = get_object_or_404(Membership, id=membership_id, task_room=room)

    if request.method == 'POST':
        if membership.status == 'pending':
            membership.status = 'accepted'
            membership.save()
            messages.success(
                request,
                f"{membership.user.username}'s request to join was accepted."
            )
        else:
            messages.info(
                request,
                f"{membership.user.username} is already an active member."
            )

    return redirect('room_detail', room_id=room.id)


# ============================================================================
# TASK MANAGEMENT VIEWS
# ============================================================================

@login_required
@user_passes_test(is_admin_or_boss)  # Only admins and bosses can assign tasks
def assign_task(request):
    """
    Assign a new task to an employee.
    Creates tasks within rooms with specified deadlines and importance levels.

    Permission logic:
    - Admin: Can assign tasks in any room
    - Boss: Can only assign tasks in rooms they created

    Task fields:
    - Title and description
    - Assigned employee (must be room member)
    - Deadline date
    - Importance level
    - Initial status
    """
    profile = request.user.profile

    # Determine available rooms based on role
    if profile.role == 'admin':
        # Admin can assign tasks in any room
        available_rooms = TaskRoom.objects.all()
    else:
        # Boss can only assign in their rooms
        available_rooms = TaskRoom.objects.filter(created_by=request.user)

    if request.method == 'POST':
        try:
            # Extract form data
            room_id = request.POST.get('task_room')
            assigned_to_id = request.POST.get('assigned_to')
            title = request.POST.get('title')
            description = request.POST.get('description')
            deadline = request.POST.get('deadline')
            importance = request.POST.get('importance')
            status = request.POST.get('status', 'pending')  # Default to pending

            # Validate and get objects
            task_room = get_object_or_404(TaskRoom, id=room_id)
            assigned_to_user = get_object_or_404(User, id=assigned_to_id)

            # Convert string date to date object
            deadline_date = date.fromisoformat(deadline)

            # Additional permission check for bosses
            if profile.role == 'boss' and task_room.created_by != request.user:
                messages.error(request, "You can only assign tasks in rooms you created.")
                return redirect('assign_task')

            # Create the task
            Task.objects.create(
                task_room=task_room,
                title=title,
                description=description,
                assigned_to=assigned_to_user,
                deadline=deadline_date,
                importance=importance,
                status=status,
            )

            messages.success(request, f"Task '{title}' has been successfully assigned.")
            return redirect('room_detail', room_id=room_id)

        except (TaskRoom.DoesNotExist, User.DoesNotExist):
            messages.error(request, "Invalid room or employee selected.")
        except ValueError:
            messages.error(request, "Invalid date format for the deadline.")

        return redirect('assign_task')

    return render(request, 'core/assign_task.html', {
        'profile': profile,
        'rooms': available_rooms,
    })


@login_required
def task_list(request):
    """
    Display tasks with filtering and statistics.
    Role-based task visibility with comprehensive filtering options.

    Task visibility:
    - Admin: All tasks in the system
    - Boss: Tasks in rooms they created
    - Employee: Tasks assigned to them

    Filtering options:
    - All tasks
    - Pending tasks (not overdue)
    - Completed tasks
    - Overdue tasks
    """
    profile = request.user.profile

    # Base queryset based on user role
    if profile.role == 'admin':
        # Admin sees all tasks with related data preloaded
        all_tasks = Task.objects.all().select_related('assigned_to', 'task_room')
    elif profile.role == 'boss':
        # Boss sees tasks in rooms they created
        all_tasks = Task.objects.filter(
            task_room__created_by=request.user
        ).select_related('assigned_to', 'task_room')
    else:  # employee
        # Employee sees only tasks assigned to them
        all_tasks = Task.objects.filter(
            assigned_to=request.user
        ).select_related('task_room')

    # Apply status filtering based on URL parameter
    status_filter = request.GET.get('status', 'all')

    if status_filter == 'pending':
        # Only pending tasks that are not overdue
        tasks = all_tasks.filter(status='pending')
    elif status_filter == 'completed':
        tasks = all_tasks.filter(status='completed')
    elif status_filter == 'overdue':
        # Tasks past deadline but not completed
        tasks = all_tasks.filter(deadline__lt=date.today(), status='pending')
    else:
        # All tasks
        tasks = all_tasks

    # Apply appropriate ordering
    if status_filter == 'completed':
        # Show most recently completed first
        tasks = tasks.order_by('-updated_at')
    else:
        # Show tasks by deadline (urgent first)
        tasks = tasks.order_by('deadline')

    # Calculate statistics for dashboard
    today = date.today()
    task_counts = {
        'all': all_tasks.count(),
        'pending': all_tasks.filter(
            status='pending',
            deadline__gte=today
        ).count(),
        'completed': all_tasks.filter(status='completed').count(),
        'overdue': all_tasks.filter(
            Q(status='pending') | Q(status='in-progress'),
            deadline__lt=today
        ).count(),
    }

    # Calculate pending review count (role-specific)
    if profile.role in ['admin', 'boss']:
        if profile.role == 'admin':
            # Admin sees all pending reviews
            pending_review_count = Submission.objects.filter(score__isnull=True).count()
        else:
            # Boss sees pending reviews in their rooms
            pending_review_count = Submission.objects.filter(
                task__task_room__created_by=request.user,
                score__isnull=True
            ).count()
    else:
        # Employee sees their submissions awaiting review
        pending_review_count = Submission.objects.filter(
            submitted_by=request.user,
            score__isnull=True
        ).count()

    return render(request, 'core/task_list.html', {
        'profile': profile,
        'tasks': tasks,
        'status_filter': status_filter,
        'task_counts': task_counts,
        'pending_review_count': pending_review_count,
    })


@login_required
def task_detail(request, task_id):
    """
    Display detailed information about a specific task.
    Shows task information, submission history, and management options.

    Access control:
    - Admin: Can view any task
    - Boss: Can view tasks in rooms they created
    - Employee: Can view tasks assigned to them

    Args:
        task_id: ID of the task to display
    """
    task = get_object_or_404(Task, id=task_id)
    profile = request.user.profile

    # Role-based permission checks
    has_access = False

    if profile.role == 'admin':
        has_access = True
    elif profile.role == 'boss' and task.task_room.created_by == request.user:
        has_access = True
    elif profile.role == 'employee' and task.assigned_to == request.user:
        has_access = True

    if not has_access:
        return HttpResponseForbidden("You do not have access to this task.")

    # Check if task is overdue
    is_overdue = (
            task.deadline < timezone.now().date() and
            task.status != 'completed'
    )

    # Get all submissions for this task
    submissions = Submission.objects.filter(task=task).order_by('-submitted_at')

    # Determine if user can manage this task
    can_manage = (
            profile.role == 'admin' or
            (profile.role == 'boss' and task.task_room.created_by == request.user)
    )

    return render(request, 'core/task_detail.html', {
        'task': task,
        'submissions': submissions,
        'is_overdue': is_overdue,
        'can_manage': can_manage,
    })


@login_required
def delete_task(request, task_id):
    """
    Delete a task.
    Only admins and room owners (bosses) can delete tasks.
    Includes confirmation step to prevent accidental deletion.

    Args:
        task_id: ID of the task to delete
    """
    task = get_object_or_404(Task, id=task_id)
    profile = request.user.profile

    # Permission check
    can_delete = False
    if profile.role == 'admin':
        can_delete = True
    elif profile.role == 'boss' and task.task_room.created_by == request.user:
        can_delete = True

    if not can_delete:
        return HttpResponseForbidden("You are not authorized to delete this task.")

    if request.method == 'POST':
        # Store task title before deletion for success message
        task_title = task.title
        task.delete()  # Cascading delete handles submissions
        messages.success(request, f"Task '{task_title}' was successfully deleted.")
        return redirect('task_list')

    # Show confirmation page on GET request
    return render(request, 'core/confirm_delete_task.html', {'task': task})


# ============================================================================
# TASK SUBMISSION & REVIEW VIEWS
# ============================================================================

@login_required
def submit_task(request, task_id):
    """
    Submit a completed task.
    Employees submit their work with optional file attachments.

    Submission process:
    1. Check if user is assigned to the task
    2. Prevent duplicate submissions
    3. Save submission with file (if provided)
    4. Update task status to 'submitted'

    Args:
        task_id: ID of the task being submitted
    """
    task = get_object_or_404(Task, id=task_id)

    # Check if user is assigned to this task
    if hasattr(task, 'assigned_to') and request.user != task.assigned_to:
        return HttpResponseForbidden("You cannot submit this task.")

    # Check for existing submission
    existing_submission = Submission.objects.filter(
        task=task,
        submitted_by=request.user
    ).first()

    if existing_submission:
        messages.info(request, "You have already submitted this task.")
        return redirect('task_list')

    if request.method == 'POST':
        # Handle file uploads and form data
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            # Create submission but don't save to DB yet
            submission = form.save(commit=False)
            submission.task = task
            submission.submitted_by = request.user

            # Store file size if file was uploaded
            if submission.file:
                submission.file_size = submission.file.size

            submission.save()

            # Update task status
            task.status = 'submitted'
            task.save()

            messages.success(request, f"Task '{task.title}' submitted successfully!")
            return redirect('task_list')
    else:
        form = SubmissionForm()

    return render(request, 'core/submit_task.html', {
        'form': form,
        'task': task
    })


@login_required
def complete_task(request, task_id):
    """
    Mark a task as completed without file submission.
    Alternative to file submission for tasks that don't require deliverables.

    Args:
        task_id: ID of the task to mark as completed
    """
    task = get_object_or_404(Task, id=task_id)

    # Check if user is assigned to this task
    if task.assigned_to != request.user:
        return HttpResponseForbidden("You are not authorized to complete this task.")

    # Check if already completed
    if task.status == 'completed':
        messages.info(request, f"Task '{task.title}' is already completed.")
        return redirect('task_list')

    if request.method == 'POST':
        # Simply mark as completed
        task.status = 'completed'
        task.save()
        messages.success(request, f"Task '{task.title}' marked as completed.")
        return redirect('task_list')

    # Show confirmation page on GET request
    return render(request, 'core/confirm_complete_task.html', {'task': task})


@login_required
def review_submission(request, submission_id):
    """
    Review and score task submissions.
    Admins and bosses can review submissions and provide feedback.

    Review process:
    1. Check permissions (admin or boss of the room)
    2. Allow scoring, completion percentage, and comments
    3. Mark task as completed when reviewed
    4. Provide feedback to the employee

    Args:
        submission_id: ID of the submission to review
    """
    submission = get_object_or_404(Submission, id=submission_id)
    profile = request.user.profile

    # Permission check using utility function
    if not can_review_submissions(request.user):
        return HttpResponseForbidden("You are not authorized to review submissions.")

    # Additional check for bosses - they can only review in their rooms
    if (profile.role == 'boss' and
            submission.task.task_room.created_by != request.user):
        return HttpResponseForbidden("You can only review submissions in your rooms.")

    if request.method == 'POST':
        # Process numerical score (0-100 or similar scale)
        try:
            score = request.POST.get('score')
            if score:
                submission.score = int(score)
        except (TypeError, ValueError):
            # Invalid score input, leave as None
            submission.score = None

        # Process completion percentage (0-100)
        try:
            completion_percentage = request.POST.get('completion_percentage')
            if completion_percentage:
                # Use Decimal for precise percentage calculations
                submission.completion_percentage = Decimal(completion_percentage)
        except (TypeError, ValueError):
            # Invalid percentage input, leave as None
            submission.completion_percentage = None

        # Process review comments (optional feedback)
        review_comments = request.POST.get('review_comments', '').strip()
        if review_comments:
            submission.review_comments = review_comments

        # Save the updated submission
        submission.save()

        # Mark associated task as completed if reviewed
        if submission.score is not None or submission.completion_percentage is not None:
            task = submission.task
            task.status = 'completed'
            task.save()
            messages.success(
                request,
                f"Submission reviewed and task '{task.title}' marked as completed!"
            )
        else:
            messages.success(request, "Submission updated successfully!")

        return redirect('task_list')

    return render(request, 'core/review_submission.html', {
        'submission': submission
    })


# ============================================================================
# API/UTILITY VIEWS
# ============================================================================

def get_employees_by_room(request):
    """
    Return JSON list of employees for a given room.
    AJAX endpoint for dynamically loading room members when assigning tasks.

    Used by the task assignment form to populate employee dropdown
    based on selected room.

    Security considerations:
    - Checks user permission to access the room
    - Only returns accepted members with employee role
    - Returns proper HTTP status codes for errors

    Returns:
        JsonResponse: List of employees with id and username
    """
    room_id = request.GET.get('room_id')
    employees = []

    if room_id:
        try:
            # Get the room first to check permissions
            room = TaskRoom.objects.get(id=room_id)

            # Check if user has permission to see room members
            if not has_room_access(request.user, room):
                return JsonResponse({'error': 'Permission denied'}, status=403)

            # Get accepted employee members of the room
            memberships = Membership.objects.filter(
                task_room__id=room_id,
                role='employee',  # Only employees can be assigned tasks
                status='accepted'  # Only accepted members
            ).select_related('user')

            # Build response data
            for membership in memberships:
                employees.append({
                    'id': membership.user.id,
                    'username': membership.user.username
                })

        except TaskRoom.DoesNotExist:
            return JsonResponse({'error': 'Room not found'}, status=404)
        except Exception as e:
            # Log error for debugging (in production, use proper logging)
            print(f"Error fetching employees: {e}")
            return JsonResponse({'error': 'Internal error'}, status=500)

    # Return JSON response (safe=False allows list serialization)
    return JsonResponse(employees, safe=False)

from django.db.models import Avg, Count, Q, Max, Min


@login_required
def room_analytics(request, room_id):
    """
    Display comprehensive analytics for a room.
    Only room owners and admins can view analytics.

    Shows:
    - Task completion statistics
    - Submission and scoring metrics
    - Member performance analysis (employees only)
    - Overall room health metrics
    - Task listings and overdue analysis
    """
    room = get_object_or_404(TaskRoom, id=room_id)

    # Check if user has permission to view analytics
    if not can_manage_room(request.user, room):
        return HttpResponseForbidden("You are not authorized to view analytics for this room.")

    # Basic task statistics
    all_tasks = Task.objects.filter(task_room=room)
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status='completed').count()
    pending_tasks = all_tasks.filter(status='pending').count()

    # Calculate overdue tasks
    today = timezone.now().date()
    overdue_tasks = all_tasks.filter(
        status='pending',
        deadline__lt=today
    ).count()

    # Submission statistics
    total_submissions = Submission.objects.filter(task__task_room=room).count()
    pending_submissions = Submission.objects.filter(task__task_room=room, score__isnull=True).count()
    reviewed_submissions = Submission.objects.filter(task__task_room=room, score__isnull=False).count()

    # Score statistics
    score_stats = Submission.objects.filter(
        task__task_room=room,
        score__isnull=False
    ).aggregate(
        average_score=Avg('score'),
        highest_score=Max('score'),
        lowest_score=Min('score'),
        total_scored=Count('id')
    )

    # Member statistics
    total_members = Membership.objects.filter(task_room=room, status='accepted').count()
    pending_members = Membership.objects.filter(task_room=room, status='pending').count()

    # Employee performance analysis (only employees)
    employee_performance = []
    employee_members = Membership.objects.filter(
        task_room=room,
        status='accepted',
        role='employee'  # Only employees
    ).select_related('user')

    # Initialize employee rankings dictionary
    employee_rankings = {
        'most_completed': [],
        'highest_completion_rate': [],
        'best_scores': [],
        'most_submissions': []
    }

    for membership in employee_members:
        member_tasks = all_tasks.filter(assigned_to=membership.user)
        completed = member_tasks.filter(status='completed').count()
        total_assigned = member_tasks.count()
        overdue_count = member_tasks.filter(
            status='pending',
            deadline__lt=today
        ).count()

        if total_assigned > 0:
            completion_rate = (completed / total_assigned) * 100
        else:
            completion_rate = 0

        # Get all submissions by this member (for submission count)
        all_member_submissions = Submission.objects.filter(
            task__task_room=room,
            submitted_by=membership.user
        )
        submission_count = all_member_submissions.count()

        # Get average score only from scored submissions
        scored_submissions = all_member_submissions.filter(score__isnull=False)
        avg_score = scored_submissions.aggregate(avg_score=Avg('score'))['avg_score']

        employee_data = {
            'member': membership.user,
            'completed': completed,
            'total_assigned': total_assigned,
            'overdue': overdue_count,
            'completion_rate': round(completion_rate, 1),
            'average_score': round(avg_score, 1) if avg_score else None,
            'submission_count': submission_count
        }

        employee_performance.append(employee_data)

        # Add to rankings (only if they have relevant data)
        if completed > 0:
            employee_rankings['most_completed'].append(employee_data)

        if total_assigned > 0:
            employee_rankings['highest_completion_rate'].append(employee_data)

        if avg_score is not None:
            employee_rankings['best_scores'].append(employee_data)

        if submission_count > 0:
            employee_rankings['most_submissions'].append(employee_data)

    # Sort and limit rankings to top 5
    employee_rankings['most_completed'] = sorted(
        employee_rankings['most_completed'],
        key=lambda x: x['completed'],
        reverse=True
    )[:5]

    employee_rankings['highest_completion_rate'] = sorted(
        employee_rankings['highest_completion_rate'],
        key=lambda x: x['completion_rate'],
        reverse=True
    )[:5]

    employee_rankings['best_scores'] = sorted(
        employee_rankings['best_scores'],
        key=lambda x: x['average_score'],
        reverse=True
    )[:5]

    employee_rankings['most_submissions'] = sorted(
        employee_rankings['most_submissions'],
        key=lambda x: x['submission_count'],
        reverse=True
    )[:5]

    # Sort employee_performance by completion rate for the main list
    employee_performance.sort(key=lambda x: x['completion_rate'], reverse=True)

    # Task importance distribution
    importance_stats = all_tasks.values('importance').annotate(
        count=Count('id')
    ).order_by('importance')

    # Recent tasks (last 10)
    recent_tasks = all_tasks.select_related(
        'assigned_to', 'task_room'
    ).order_by('-created_at')[:10]

    # Overdue tasks details
    overdue_task_details = all_tasks.filter(
        status='pending',
        deadline__lt=today
    ).select_related('assigned_to').order_by('deadline')

    # Pending submissions details
    pending_submission_details = Submission.objects.filter(
        task__task_room=room,
        score__isnull=True
    ).select_related('task', 'submitted_by').order_by('-submitted_at')

    # Task status breakdown for chart
    task_status_data = {
        'completed': completed_tasks,
        'pending': pending_tasks - overdue_tasks,  # pending but not overdue
        'overdue': overdue_tasks
    }

    context = {
        'room': room,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks,
        'completion_rate': round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0,
        'total_submissions': total_submissions,
        'pending_submissions': pending_submissions,
        'reviewed_submissions': reviewed_submissions,
        'average_score': round(score_stats['average_score'] or 0, 2),
        'highest_score': score_stats['highest_score'] or 0,
        'lowest_score': score_stats['lowest_score'] or 0,
        'total_members': total_members,
        'pending_members': pending_members,
        'employee_performance': employee_performance,
        'employee_rankings': employee_rankings,  # ADD THIS LINE
        'importance_stats': importance_stats,
        'recent_tasks': recent_tasks,
        'overdue_task_details': overdue_task_details,
        'pending_submission_details': pending_submission_details,
        'task_status_data': task_status_data,
        'is_owner': room.created_by == request.user,
    }

    return render(request, 'core/room_analytics.html', context)


@login_required
@user_passes_test(is_employee)
def employee_analytics(request, room_id=None):
    user = request.user
    today = timezone.now().date()

    # If room-specific analytics is requested
    room = None
    if room_id:
        room = get_object_or_404(TaskRoom, id=room_id)

        # Check membership
        membership = Membership.objects.filter(
            user=user, task_room=room, status='accepted'
        ).first()

        if not membership:
            return HttpResponseForbidden("You are not a member of this room.")

        # Tasks only inside this room
        tasks = Task.objects.filter(task_room=room, assigned_to=user)
    else:
        # Global tasks for employee
        tasks = Task.objects.filter(assigned_to=user)

    # Basic Stats
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    pending_tasks = tasks.filter(status='pending').count()
    overdue_tasks = tasks.filter(status='pending', deadline__lt=today).count()

    completion_rate = (
        round((completed_tasks / total_tasks) * 100, 1)
        if total_tasks > 0 else 0
    )

    # Submissions
    submissions = Submission.objects.filter(submitted_by=user)
    if room:
        submissions = submissions.filter(task__task_room=room)

    total_submissions = submissions.count()
    pending_review_submissions = submissions.filter(score__isnull=True).count()
    reviewed_submissions = submissions.filter(score__isnull=False).count()

    avg_score = submissions.filter(score__isnull=False).aggregate(
        avg=Avg('score')
    )['avg']
    avg_score = round(avg_score, 1) if avg_score else 0

    # Recent tasks
    recent_tasks = tasks.order_by('-created_at')[:10]

    # Rooms joined
    rooms_joined = Membership.objects.filter(
        user=user,
        status='accepted'
    ).count()

    # ============ EMPLOYEE RANKINGS ============
    employee_rankings = {
        'most_completed': [],
        'highest_completion_rate': [],
        'best_scores': [],
        'most_submissions': []
    }

    user_top_rankings = []  # Track categories where user is #1

    if room:
        # Get all employees in this room
        employee_members = Membership.objects.filter(
            task_room=room,
            status='accepted',
            role='employee'
        ).select_related('user')

        all_room_tasks = Task.objects.filter(task_room=room)

        for membership in employee_members:
            member_tasks = all_room_tasks.filter(assigned_to=membership.user)
            completed = member_tasks.filter(status='completed').count()
            total_assigned = member_tasks.count()

            if total_assigned > 0:
                completion_rate_member = (completed / total_assigned) * 100
            else:
                completion_rate_member = 0

            # Get submissions
            member_submissions = Submission.objects.filter(
                task__task_room=room,
                submitted_by=membership.user
            )
            submission_count = member_submissions.count()

            # Get average score
            scored_submissions = member_submissions.filter(score__isnull=False)
            avg_score_member = scored_submissions.aggregate(avg_score=Avg('score'))['avg_score']

            employee_data = {
                'member': membership.user,
                'completed': completed,
                'total_assigned': total_assigned,
                'completion_rate': round(completion_rate_member, 1),
                'average_score': round(avg_score_member, 1) if avg_score_member else None,
                'submission_count': submission_count
            }

            # Add to rankings
            if completed > 0:
                employee_rankings['most_completed'].append(employee_data)

            if total_assigned > 0:
                employee_rankings['highest_completion_rate'].append(employee_data)

            if avg_score_member is not None:
                employee_rankings['best_scores'].append(employee_data)

            if submission_count > 0:
                employee_rankings['most_submissions'].append(employee_data)

        # Sort and limit to top 5
        employee_rankings['most_completed'] = sorted(
            employee_rankings['most_completed'],
            key=lambda x: x['completed'],
            reverse=True
        )[:5]

        employee_rankings['highest_completion_rate'] = sorted(
            employee_rankings['highest_completion_rate'],
            key=lambda x: x['completion_rate'],
            reverse=True
        )[:5]

        employee_rankings['best_scores'] = sorted(
            employee_rankings['best_scores'],
            key=lambda x: x['average_score'],
            reverse=True
        )[:5]

        employee_rankings['most_submissions'] = sorted(
            employee_rankings['most_submissions'],
            key=lambda x: x['submission_count'],
            reverse=True
        )[:5]

        # Check if user is #1 in any category
        if employee_rankings['most_completed'] and employee_rankings['most_completed'][0]['member'] == user:
            user_top_rankings.append("Most Tasks Completed 🎯")

        if employee_rankings['highest_completion_rate'] and employee_rankings['highest_completion_rate'][0][
            'member'] == user:
            user_top_rankings.append("Best Completion Rate ⚡")

        if employee_rankings['best_scores'] and employee_rankings['best_scores'][0]['member'] == user:
            user_top_rankings.append("Top Performer ⭐")

        if employee_rankings['most_submissions'] and employee_rankings['most_submissions'][0]['member'] == user:
            user_top_rankings.append("Most Active 📝")

    context = {
        'room': room,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks,
        'completion_rate': completion_rate,
        'total_submissions': total_submissions,
        'reviewed_submissions': reviewed_submissions,
        'pending_review_submissions': pending_review_submissions,
        'avg_score': avg_score,
        'recent_tasks': recent_tasks,
        'rooms_joined': rooms_joined,
        'employee_rankings': employee_rankings,  # NEW
        'user_top_rankings': user_top_rankings,  # NEW
        'today': today
    }

    return render(request, 'core/employee_analytics.html', context)