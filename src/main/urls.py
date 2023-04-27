from django.conf.urls import include
from django.urls import re_path


# api and auth routes
urlpatterns = [
    re_path("^api/", include("ams.urls")),
    re_path("^auth/", include("authconf.auth_urls"))
]
