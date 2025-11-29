# Django imports
from django.db import models


class Store(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


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

    def __str__(self):
        return f"{self.name} - "

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["name"]),
            models.Index(fields=["price"]),
        ]


class Inventory(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="inventory_items"
    )
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="inventory")
    quantity = models.IntegerField(default=0)
    min_stock = models.IntegerField(default=0)

    class Meta:
        unique_together = ("product", "store")

    def __str__(self):
        return f"{self.product.name} - {self.store.name} ({self.quantity})"


class Movement(models.Model):
    MOVEMENT_TYPES = (
        ("IN", "Entrada"),
        ("OUT", "Salida"),
        ("TRANSFER", "Transferencia"),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    source_store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movement_source",
    )
    target_store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movement_target",
    )
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)

    def __str__(self):
        return f"{self.product.name} - {self.type} ({self.quantity})"
