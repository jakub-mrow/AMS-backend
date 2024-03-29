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
router.register(r'favourite_assets', views.FavoriteAssetViewSet, "favourite_assets")

urlpatterns = [
    re_path("", include(router.urls)),
    re_path(r'search', views.StockSearchAPIView.as_view(), name='api-search'),
    re_path(r'get_stock_details', views.StockDetailsAPIView.as_view(), name='get_stock_details'),
    re_path(r'get_stock_history', views.StockPriceHistoryAPIView.as_view(), name='get_stock_history'),
    re_path(r'get_stock_news', views.StockNewsAPIView.as_view(), name='get_stock_news'),
    re_path(r'update_stock', views.update_stock, name='update_stock'),
    re_path(r'accounts/(?P<account_id>\d+)/history', views.AccountHistoryView.as_view(), name="account_history"),
    re_path(r'import_stock_transactions', views.stock_transactions, name="import_stock_transactions"),
    re_path(r'(?P<account_id>\d+)/import_csv_stock_transactions', views.csv_stock_transactions, name="import_csv_stock_transactions"),
]