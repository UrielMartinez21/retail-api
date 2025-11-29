from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.all_products, name='all_products'),
    path('<int:product_id>/', views.product_detail, name='product_detail'),
]
