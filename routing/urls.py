from django.urls import path
from . import views

urlpatterns = [
    path('api/routing/estimate/', views.estimate_route_api, name='api_estimate_route'),
]
