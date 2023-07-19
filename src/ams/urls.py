from django.conf.urls import include
from django.urls import re_path
from rest_framework.routers import DefaultRouter

from ams import views

router = DefaultRouter(trailing_slash=False)
router.register("tasks", views.TaskViewSet, "task")

urlpatterns = [
    re_path("", include(router.urls))
]