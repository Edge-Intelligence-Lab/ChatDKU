from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid
# Create your models here.
User = get_user_model()

class Feedback(models.Model):
    id=models.AutoField(primary_key=True)
    user_input=models.TextField(null=False,blank=False)
    gen_answer=models.TextField(null=False)
    feedback_reason=models.TextField("Feedback reason")
    question_id=models.TextField("Question ID")
    time=models.DateTimeField(default=timezone.now)

class UserSession(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user=models.ForeignKey(User, null=False, on_delete=models.CASCADE,related_name="usersession")
    created_at=models.DateTimeField(auto_now_add=True)
    title=models.CharField(max_length=100, null=False)

    def __str__(self):
        return f"Session {self.id} - {self.title}"

class ChatMessages(models.Model):
    session=models.ForeignKey(to=UserSession,on_delete=models.CASCADE,related_name="messages")
    role=models.CharField(max_length=20,choices=[("user","User"),("bot","Bot")])
    message=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)

