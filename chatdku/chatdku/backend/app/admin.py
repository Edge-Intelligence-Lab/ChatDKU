from flask_admin.contrib.sqla import ModelView

class AdminView(ModelView):
    can_create=False
    can_delete=True
    can_edit=False
    can_export=True
    