from django.urls import path
from . import views
from . import api

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('graph/<str:metric>/', views.graph, name='graph'),
    path('graph/<str:metric>/csv/', views.export_csv, name='export_csv'),
    path('test/', views.test, name='test'),
    path("api/get", api.Dlist, name='json'),
    path("api/post", api.Dhtviews.as_view(), name='json'),
    path("api/latest", api.Dlatest, name='latest'),
    path("api/history", api.Dhistory, name="history"),
]
