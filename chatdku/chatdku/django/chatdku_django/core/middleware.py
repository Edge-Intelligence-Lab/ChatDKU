from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from core.models import hash_netid

User = get_user_model()

class NetIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path_parts = [p for p in request.path.strip('/').split('/')]
        if   any(part in ("admin","doc","metrics") for part in path_parts):
            return self.get_response(request)

        
        netid = request.META.get("HTTP_UID") or request.session.get("netid")
        display_name = request.META.get("HTTP_X_DISPLAYNAME")
        setattr(request, '_dont_enforce_csrf_checks', True)


        if not netid:
            return JsonResponse({"message": "Unauthorized"}, status=401)

        user, created = User.objects.get_or_create_by_netid(netid)

        if not request.user.is_authenticated or request.user.username != hash_netid(netid):
            login(request, user)

        request.netid = user.username
        request.session["netid"] = netid
        if display_name:
            request.session["display_name"] = display_name

        return self.get_response(request)

