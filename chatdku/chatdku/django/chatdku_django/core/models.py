from django.db import models
from django.contrib.auth.models import AbstractBaseUser,BaseUserManager,PermissionsMixin
from django.utils import timezone
from django.conf import settings
import uuid
import hashlib
import os
import re
from django_prometheus.models import ExportModelOperationsMixin

#helper function and class
def generate_uuid_string():
    return str(uuid.uuid4())


#Hashing function

def hash_netid(netid: str) -> str:
    return hashlib.sha256(netid.encode('utf-8')).hexdigest()

# Create your models here.

class ChatDkuUserManager(BaseUserManager):
    def create_user(self,netid,password=None,hash_user=True,**kwargs):
        if not netid:
            raise ValueError("Netid Required")
        
        if hash_user:
            hashed_netid=hash_netid(netid)
        else:
            hashed_netid=netid    

        user=self.model(username=hashed_netid,**kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, password=None, **kwargs):
        kwargs.setdefault('is_staff', True)
        kwargs.setdefault('is_admin', True)
        kwargs.setdefault('is_superuser', True)

        if not kwargs.get("email"):
            raise ValueError("Superusers must have an email address.")

        return self.create_user(username, password=password,hash_user=False, **kwargs)


    def get_or_create_by_netid(self, netid, password=None, **kwargs):
        if re.search(r'admin',netid):
            hashed_netid=netid
        else:    
            hashed_netid = hash_netid(netid)
        user, created = self.get_or_create(username=hashed_netid, defaults={**kwargs})
        if created and password:
            user.set_password(password)
            user.save(using=self._db)
        return user, created

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


    def set_netid(self,netid:str):
        self.username=hash_netid(netid)

    def check_netid(self,netid:str)->bool:
        return self.username==hash_netid(netid)

    def __str__(self):
        return self.username

    @classmethod
    def get_by_netid(cls,netid):
        return cls.objects.get(username=hash_netid(netid))
    
    @classmethod
    def get_or_create_by_netid(cls,netid,password=None):
        hashed_netid=hash_netid(netid)
        user,created=cls.objects.get_or_create(username=hashed_netid)
        if created and password:
            user.set_password(password)
            user.save()

        return user
    
    @classmethod
    def exists(cls,netid):
        return cls.objects.filter(username=hash_netid(netid)).exists()



class UploadedFile(ExportModelOperationsMixin('uploadfile'),models.Model):
    id=models.AutoField(primary_key=True)
    filename=models.CharField(max_length=200,unique=True,null=False)
    uploaded_time=models.DateTimeField(default=timezone.now)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="files")


    def delete(self,*args,**kwargs):
        filepath=os.path.join(settings.MEDIA_ROOT,self.user.folder,self.filename)
        print(filepath)

        if os.path.exists(filepath):
            os.remove(filepath)

        super().delete(*args,**kwargs)
