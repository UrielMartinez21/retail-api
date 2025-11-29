from django.db import models


class Product(models.Model):
    class Category(models.TextChoices):
        ELECTRONICS = "EL", "Electronics"
        FASHION = "FA", "Fashion"
        HOME = "HO", "Home"
        TOYS = "TO", "Toys"
        SPORTS = "SP", "Sports"

    name = models.CharField(max_length=100, verbose_name="Nombre del Producto")
    description = models.TextField(verbose_name="Descripción del Producto")
    category = models.CharField(
        max_length=2,
        choices=Category.choices,
        default=Category.HOME,
        verbose_name="Categoría",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Cantidad en Stock")

    def __str__(self):
        return f"{self.name} - "

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["stock_quantity"]),
            models.Index(fields=["category"]),
            models.Index(fields=["name"]),
            models.Index(fields=["price"]),
        ]
