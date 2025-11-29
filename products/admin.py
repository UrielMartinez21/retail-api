from django.contrib import admin
from .models import Product, Store, Inventory, Movement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price")
    search_fields = ("name", "sku")
    list_filter = ("category",)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "address")
    search_fields = ("name",)


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("product", "store", "quantity", "min_stock")
    search_fields = ("product__name", "store__name")
    list_filter = ("store",)


@admin.register(Movement)
class MovementAdmin(admin.ModelAdmin):
    list_display = ("product", "type", "quantity", "timestamp")
    search_fields = ("product__name",)
    list_filter = ("type", "timestamp")
