from django.urls import path
from . import views

app_name = 'pilots'

urlpatterns = [
    path('', views.PilotListView.as_view(), name='list'),
    path('<int:pk>/', views.PilotDetailView.as_view(), name='detail'),
]