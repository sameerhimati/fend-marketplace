from django.urls import path
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
]