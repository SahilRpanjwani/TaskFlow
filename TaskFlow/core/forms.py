# In your app's forms.py

from django import forms
from .models import TaskRoom
from .models import Profile
from django.contrib.auth.models import User
from .models import Task, Submission


class TaskRoomForm(forms.ModelForm):
    class Meta:
        model = TaskRoom
        fields = ['name', 'description', 'is_public']


class UserRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    ROLE_CHOICES_REGISTER = (
        ('boss', 'Boss'),
        ('employee', 'Employee'),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES_REGISTER)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['task_room', 'assigned_to', 'title', 'description', 'deadline', 'importance']


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['file']