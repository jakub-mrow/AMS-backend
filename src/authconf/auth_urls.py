from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from authconf import auth_views

urlpatterns = [
    path('login', auth_views.LoginView.as_view(), name='login'),
    path('register', auth_views.RegisterView.as_view(), name='auth_register'),
    path('login/refresh', TokenRefreshView.as_view(), name='token_refresh')
]