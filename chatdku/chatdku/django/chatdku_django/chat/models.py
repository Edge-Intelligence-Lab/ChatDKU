from django.db import models
from django.utils import timezone
# Create your models here.

class Feedback(models.Model):
    id=models.AutoField(primary_key=True)
    user_input=models.TextField(null=False,blank=False)
    gen_answer=models.TextField(null=False)
    feedback_reason=models.TextField("Feedback reason")
    question_id=models.IntegerField("Question ID")
    time=models.DateTimeField(default=timezone.now)
