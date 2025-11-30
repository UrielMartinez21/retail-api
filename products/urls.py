from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('products/', views.products, name='products'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),

    path('stores/', views.stores, name='stores'),
    path('stores/<int:store_id>/inventory/', views.store_inventory, name='store_inventory'),
    path('inventory/transfer/', views.transfer_inventory, name='transfer_inventory'),
    path('inventory/alerts/', views.inventory_alerts, name='inventory_alerts'),
    path('movements/', views.movements, name='movements'),
]
