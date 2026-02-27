import os
from django.contrib import admin
from core.models import UserModel, UploadedFile
from django.contrib.auth.admin import UserAdmin


# Site
admin.site.site_url = os.getenv("ADMIN_SITE_URL", "http://localhost:8000")

# Register your models here.
@admin.register(UserModel)
class ChatDkuUserAdmin(UserAdmin):
    list_display = ('username', 'is_staff', 'is_active','email')
    readonly_fields = ('folder', 'last_login')
    search_fields = ('username','email')
    ordering = ('username','email')
    fieldsets = (
        (None, {'fields': ('username','email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Custom Info', {'fields': ('folder', 'last_login')}),
    )

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj = None):
        if obj:
            return self.readonly_fields + ("username",)
        return self.readonly_fields

    
@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'uploaded_time', 'user')
    search_fields = ('filename', 'user__username') 
    list_filter = ('uploaded_time',)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()  


