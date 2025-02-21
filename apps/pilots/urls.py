from django.urls import path
from . import views

app_name = 'pilots'

urlpatterns = [
    path('', views.PilotListView.as_view(), name='list'),
    path('create/', views.PilotCreateView.as_view(), name='create'),
    path('<int:pk>/', views.PilotDetailView.as_view(), name='detail'),
    path('<int:pk>/publish/', views.publish_pilot, name='publish'),
    path('<int:pilot_id>/bid/', views.create_bid, name='create_bid'),
    path('bids/', views.BidListView.as_view(), name='bid_list'),
    path('bids/<int:pk>/', views.BidDetailView.as_view(), name='bid_detail'),
    path('bids/<int:pk>/update-status/', views.update_bid_status, name='update_bid_status'),
    path('<int:pk>/edit/', views.PilotUpdateView.as_view(), name='edit'),
    path('bids/<int:pk>/delete/', views.delete_bid, name='delete_bid'),
    path('pilots/<int:pk>/delete/', views.delete_pilot, name='delete'),
]