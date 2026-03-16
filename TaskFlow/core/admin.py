from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import TaskRoom, Membership, Submission

@admin.register(TaskRoom)
class TaskRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at')
    search_fields = ('name', 'created_by__username')

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'task_room', 'role', 'joined_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'task_room__name')

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('submitted_by', 'get_task_room', 'file', 'file_size', 'submitted_at')
    search_fields = ('submitted_by__username', 'task__task_room__name')

    def get_task_room(self, obj):
        return obj.task.task_room.name
    get_task_room.short_description = 'Task Room'
