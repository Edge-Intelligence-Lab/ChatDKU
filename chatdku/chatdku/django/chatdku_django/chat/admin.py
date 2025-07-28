from import_export.admin import ExportMixin
from django.contrib import admin
from chat.models import Feedback

# Register your models here.
@admin.register(Feedback)
class FeedbackAdmin(ExportMixin,admin.ModelAdmin):
    list_display=['id','time','user_input','gen_answer','feedback_reason','question_id']
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request,obj=None):
        return False