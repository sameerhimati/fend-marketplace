from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'organizations'

urlpatterns = [
     path('register/', 
         views.OrganizationRegistrationView.as_view(), 
         name='register'),
     path('register/<int:pk>/enterprise/', 
         views.EnterpriseDetailsView.as_view(), 
         name='enterprise_details'),
     path('register/<int:pk>/pilot-definition/', 
         views.PilotDefinitionView.as_view(), 
         name='pilot_definition'),
     path('register/complete/',
         views.RegistrationCompleteView.as_view(),
         name='registration_complete'),
     path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
     path('dashboard/enterprise/', views.EnterpriseDashboardView.as_view(), name='enterprise_dashboard'),
     path('dashboard/startup/', views.StartupDashboardView.as_view(), name='startup_dashboard'),
     path('login/', views.CustomLoginView.as_view(), name='login'),
     path('logout/', LogoutView.as_view(next_page='landing'), name='logout'),
     path('enterprises/', views.EnterpriseDirectoryView.as_view(), name='enterprise_directory'),
     path('profile/<int:pk>/', views.OrganizationProfileView.as_view(), name='profile'),
     path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
]