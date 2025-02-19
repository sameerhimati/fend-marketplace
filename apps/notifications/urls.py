from django.urls import path
from apps.notifications import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('<int:notification_id>/', views.notification_detail, name='detail'),
    path('<int:notification_id>/read/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    path('count/', views.get_notification_count, name='count'),
    path('<int:notification_id>/delete/', views.delete_notification, name='delete'),
    path('toggle/', views.toggle_notifications, name='toggle'),
]