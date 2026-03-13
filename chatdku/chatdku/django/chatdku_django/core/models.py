from django.db import models
from django.contrib.auth.models import AbstractBaseUser,BaseUserManager,PermissionsMixin
from django.utils import timezone
from django.conf import settings
import uuid
import os
from django_prometheus.models import ExportModelOperationsMixin

#helper function and class
def generate_uuid_string():
    return str(uuid.uuid4())


# Simplified user manager without NetID hashing
class ChatDkuUserManager(BaseUserManager):
    def create_user(self, username, password=None, **kwargs):
        if not username:
            raise ValueError("Username Required")

        user = self.model(username=username, **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **kwargs):
        kwargs.setdefault('is_staff', True)
        kwargs.setdefault('is_admin', True)
        kwargs.setdefault('is_superuser', True)

        if not kwargs.get("email"):
            raise ValueError("Superusers must have an email address.")

        return self.create_user(username, password=password, **kwargs)


class UserModel(ExportModelOperationsMixin('user'),AbstractBaseUser,PermissionsMixin):
    username=models.CharField(max_length=100,unique=True)
    email=models.EmailField(blank=True,unique=True,null=True)
    is_active=models.BooleanField(default=True)
    is_staff=models.BooleanField(default=False)
    is_admin=models.BooleanField(default=False)
    folder=models.CharField(default=generate_uuid_string)

    USERNAME_FIELD="username"
    REQUIRED_FIELDS=[]

    objects=ChatDkuUserManager()

    def __str__(self):
        return self.username


class UploadedFile(ExportModelOperationsMixin('uploadfile'),models.Model):
    id=models.AutoField(primary_key=True)
    filename=models.CharField(max_length=200,unique=True,null=False)
    uploaded_time=models.DateTimeField(default=timezone.now)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="files",null=True,blank=True)


    def delete(self,*args,**kwargs):
        # Use shared upload folder
        filepath=os.path.join(settings.MEDIA_ROOT, "uploads", self.filename)
        print(filepath)

        if os.path.exists(filepath):
            os.remove(filepath)

        super().delete(*args,**kwargs)
