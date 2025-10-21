from django.contrib import admin
from .models import Task

admin.site.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'created_at')
    search_fields = ('title', 'status')