"""URL configuration for myproject.

Mounts the wrapper-shared API at ``/api/`` plus the bare ``/`` and
``/health`` info endpoints. The admin lives at ``/admin/`` for
local dev / debugging.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def index(_request):
    return JsonResponse({
        "project": "python-django-skel",
        "version": "1.0.0",
        "framework": "Django",
        "status": "running",
    })


def health(_request):
    return JsonResponse({"status": "healthy"})


urlpatterns = [
    path("", index, name="index"),
    path("health", health, name="health"),
    path("api/", include("app.urls")),
    path("admin/", admin.site.urls),
]
