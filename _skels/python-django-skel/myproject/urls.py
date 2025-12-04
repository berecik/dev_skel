"""URL configuration for myproject."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def index(request):
    """Root endpoint returning project info."""
    return JsonResponse({
        "project": "python-django-skel",
        "version": "1.0.0",
        "framework": "Django",
        "status": "running",
    })


def health(request):
    """Health check endpoint."""
    return JsonResponse({"status": "healthy"})


urlpatterns = [
    path("", index, name="index"),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
]
