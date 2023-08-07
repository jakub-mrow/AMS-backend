from django.conf.urls import include
from django.urls import re_path
from rest_framework.routers import DefaultRouter

from ams import views

router = DefaultRouter(trailing_slash=False)
router.register("tasks", views.TaskViewSet, "task")
router.register("accounts", views.AccountViewSet, "account")
router.register(r'accounts/(?P<account_id>\d+)/deposit', views.DepositViewSet, "deposit")
router.register(r'accounts/(?P<account_id>\d+)/withdrawal', views.WithdrawalViewSet, "withdrawal")
router.register(r'accounts/(?P<account_id>\d+)/transactions', views.TransactionViewSet, "transaction")
router.register("exchanges", views.ExchangeViewSet, "exchange")


urlpatterns = [
    re_path("", include(router.urls)),
]
