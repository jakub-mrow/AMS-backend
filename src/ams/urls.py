from django.conf.urls import include
from django.urls import re_path, path
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from ams import views


router = DefaultRouter(trailing_slash=False)
router.register("accounts", views.AccountViewSet, "account")
router.register(r'accounts/(?P<account_id>\d+)/transactions', views.TransactionViewSet, "transaction")
urlpatterns = [
    re_path("", include(router.urls)),

]
