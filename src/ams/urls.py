from django.conf.urls import include
from django.urls import re_path
from rest_framework.routers import DefaultRouter

from ams import views

router = DefaultRouter(trailing_slash=False)
router.register("accounts", views.AccountViewSet, "account")
router.register(r'accounts/(?P<account_id>\d+)/transactions', views.TransactionViewSet, "transaction")
router.register("exchanges", views.ExchangeViewSet, "exchange")
router.register("stocks", views.StockViewSet, "stock")
router.register(r'stocks/(?P<exchange_id>\d+)', views.StockViewSet, "stocks_by_exchange"),
router.register(r'stock/(?P<account_id>\d+)/transaction', views.StockTransactionViewSet, "transaction")
router.register(r'stock_balances/(?P<account_id>\d+)', views.StockBalanceViewSet, "stock_balance")


urlpatterns = [
    re_path("", include(router.urls)),
    re_path(r'search', views.StockSearchAPIView.as_view(), name='api-search')
]
