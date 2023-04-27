from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny

from django.contrib.auth.models import User

from rest_framework import generics

from .auth_serializers import TokenObtainSerializer, RegisterSerializer


class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny, )
    serializer_class = TokenObtainSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny, )
    serializer_class = RegisterSerializer


