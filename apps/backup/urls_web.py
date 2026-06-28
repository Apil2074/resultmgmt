from django.urls import path
from .views_web import backup_index, create_backup, restore_backup
urlpatterns = [path('', backup_index, name='backup_index'), path('create/', create_backup, name='create_backup'), path('restore/', restore_backup, name='restore_backup'),]
