from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid
from django_prometheus.models import ExportModelOperationsMixin

# Create your models here.
User = get_user_model()


class Feedback(ExportModelOperationsMixin("feedback"), models.Model):
    id = models.AutoField(primary_key=True)
    user_input = models.TextField(null=False, blank=False)
    gen_answer = models.TextField(null=False)
    feedback_reason = models.TextField("Feedback reason")
    question_id = models.TextField("Question ID")
    time = models.DateTimeField(default=timezone.now)


class UserSession(ExportModelOperationsMixin("usersession"), models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, null=False, on_delete=models.CASCADE, related_name="usersession"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, null=False)

    def __str__(self):
        return f"Session {self.id} - {self.title}"


class ChatMessages(ExportModelOperationsMixin("chat"), models.Model):
    USER = "user"
    BOT = "bot"

    ROLE_CHOICES = [(USER, "User"), (BOT, "Bot")]

    session = models.ForeignKey(
        to=UserSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class WeeklyEvent(models.Model):
    title = models.CharField(max_length=500)
    event_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    sponsor = models.CharField(max_length=200, blank=True)
    open_to = models.CharField(max_length=200, blank=True)
    speaker = models.CharField(max_length=200, blank=True)
    url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'weekly_events'
        managed = False          # 表已存在，Django 不管理迁移
        ordering = ['event_date', 'start_time']