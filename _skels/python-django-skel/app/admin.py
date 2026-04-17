"""Admin registration for the wrapper-shared models."""

from django.contrib import admin

from app.models import Category, Item, ReactState

admin.site.register(Category)
admin.site.register(Item)
admin.site.register(ReactState)
