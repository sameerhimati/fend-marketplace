from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Password management
    path('password/change/', views.password_change_redirect, name='password_change_redirect'),
    path('password/change/normal/', views.PasswordChangeView.as_view(), name='password_change'),
    path('password/change/force/', views.ForcePasswordChangeView.as_view(), name='force_password_change'),
]