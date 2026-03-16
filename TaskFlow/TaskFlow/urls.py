# TaskFlow/urls.py

from django.contrib import admin
from django.urls import path
from core import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('create-room/', views.create_room, name='create_room'),
    path('rooms/', views.room_list, name='room_list'),
    path('join-room/', views.join_room, name='join_room'),
    path('tasks/', views.task_list, name='task_list'),
    path('submit-task/<int:task_id>/', views.submit_task, name='submit_task'),
    path('review-submission/<int:submission_id>/', views.review_submission, name='review_submission'),
    path('rooms/<int:room_id>/', views.room_detail, name='room_detail'),
    path('room/<int:room_id>/analytics/', views.room_analytics, name='room_analytics'),
    path('', views.home, name='home'),

    # URL patterns for task actions
    path('tasks/complete/<int:task_id>/', views.complete_task, name='complete_task'),
    path('tasks/delete/<int:task_id>/', views.delete_task, name='delete_task'),
    path('room/<int:room_id>/delete/', views.delete_room, name='delete_room'),
    path('get_employees_by_room/', views.get_employees_by_room, name='get_employees_by_room'),
    path('assign-task/', views.assign_task, name='create_task'),
    path('task/<int:task_id>/', views.task_detail, name='task_detail'),
    path('rooms/<int:room_id>/remove_member/', views.remove_member, name='remove_member'),
    path('rooms/<int:room_id>/edit/', views.edit_room, name='edit_room'),
    path('rooms/<int:room_id>/members/<int:membership_id>/accept/', views.accept_member, name='accept_member'),
    # Employee Analytics URLs
    path('employee/analytics/', views.employee_analytics, name='employee_analytics'),
    path('employee/analytics/<int:room_id>/', views.employee_analytics, name='employee_analytics_room'),


    # Admin-only URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('change-user-role/<int:user_id>/', views.change_user_role, name='change_user_role'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('system-overview/', views.system_overview, name='system_overview'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
