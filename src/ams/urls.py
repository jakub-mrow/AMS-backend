from django.conf.urls import include
from django.urls import re_path, path
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from ams import views

schema_view = get_schema_view(
    openapi.Info(
        title="AMS-backend",
        default_version='v1'
    ),
    public=True,
)


router = DefaultRouter(trailing_slash=False)
router.register("tasks", views.TaskViewSet, "task")
router.register("accounts", views.AccountViewSet, "account")
router.register(r'accounts/(?P<account_id>\d+)/deposit', views.DepositViewSet, "deposit")
router.register(r'accounts/(?P<account_id>\d+)/withdrawal', views.WithdrawalViewSet, "withdrawal")
router.register(r'accounts/(?P<account_id>\d+)/transactions', views.TransactionViewSet, "transaction")


urlpatterns = [
    re_path("", include(router.urls)),

    re_path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),

]
