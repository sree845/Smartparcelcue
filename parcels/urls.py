from django.urls import path
from .import views
urlpatterns=[
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register_parcel/', views.register_parcel, name='register_parcel'),
    path('my_parcels/', views.my_parcels, name='my_parcels'),
    path('cancel/<int:parcel_id>/', views.cancel_parcel, name='cancel_parcel'),
    path('reschedule_parcel/<int:booking_id>/', views.reschedule_parcel, name='reschedule_parcel'),
    path('update-status/<int:booking_id>/', views.update_status, name='update_status'),
]