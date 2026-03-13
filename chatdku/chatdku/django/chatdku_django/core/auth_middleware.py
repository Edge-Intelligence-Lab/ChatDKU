from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()

class UIDAuthenticationMiddleware:
    """从 UID header 自动认证用户"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        uid = request.META.get('HTTP_UID')

        if uid:
            # 从 UID 获取或创建用户
            user, _ = User.objects.get_or_create(username=uid)
            request.user = user
            request.netid = uid
        else:
            # 没有 UID，设置为匿名用户
            request.user = AnonymousUser()

        return self.get_response(request)
