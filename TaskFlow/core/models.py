from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid


# Profile to store user roles
class Profile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('boss', 'Boss'),
        ('employee', 'Employee'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


# Auto-create profile when new user is made
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


# Stores each office/college task room
class TaskRoom(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)  # Boss/Admin
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=True)
    room_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return self.name


# Stores which user is in which room and their role
class Membership(models.Model):
    ROLE_CHOICES = (
        ('boss', 'Boss'),
        ('employee', 'Employee'),
    )
    MEMBERSHIP_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task_room = models.ForeignKey(TaskRoom, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='employee')
    status = models.CharField(max_length=10, choices=MEMBERSHIP_STATUS_CHOICES, default='accepted')
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.task_room.name}"


# Stores uploaded submissions for tasks
class Submission(models.Model):
    task = models.ForeignKey('Task', on_delete=models.CASCADE)
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='submissions/')
    file_size = models.BigIntegerField(null=True, blank=True)  # in bytes
    submitted_at = models.DateTimeField(auto_now_add=True)

    # Grading fields
    score = models.IntegerField(null=True, blank=True)  # out of 100
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Submission by {self.submitted_by.username} for {self.task.title}"

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)


# Importance choices for tasks
IMPORTANCE_CHOICES = (
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
)


class Task(models.Model):
    task_room = models.ForeignKey(TaskRoom, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)
    deadline = models.DateField()
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], default='pending')
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default='medium')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.assigned_to.username}"
