import re
from django.contrib.auth import get_user_model

User=get_user_model()



def slugify(name: str) -> str:
    name = name.replace(" ", "-").strip()
    name=name.replace("-","_").strip("_")
    clean_text = re.sub(r'[^a-zA-Z0-9\s_]', '', name)
    return clean_text


def get_admin_email():
    admin_emails=list(User.objects.filter(email__isnull=False).exclude(email="").values_list("email", flat=True))
    return admin_emails


