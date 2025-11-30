"""
Factory classes for creating test data using factory_boy and Faker
"""

import factory
from factory import fuzzy
from faker import Faker
from decimal import Decimal

from products.models import Store, Product, Inventory, Movement

fake = Faker()


class StoreFactory(factory.django.DjangoModelFactory):
    """Factory for creating Store instances"""
    
    class Meta:
        model = Store
    
    name = factory.LazyFunction(lambda: fake.company())
    address = factory.LazyFunction(lambda: fake.address())


class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for creating Product instances"""
    
    class Meta:
        model = Product
    
    name = factory.LazyFunction(lambda: fake.catch_phrase())
    description = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    category = fuzzy.FuzzyChoice([choice[0] for choice in Product.Category.choices])
    price = factory.LazyFunction(lambda: Decimal(str(fake.pydecimal(left_digits=3, right_digits=2, positive=True))))
    sku = factory.LazyFunction(lambda: fake.unique.lexify(text='???-###'))


class InventoryFactory(factory.django.DjangoModelFactory):
    """Factory for creating Inventory instances"""
    
    class Meta:
        model = Inventory
    
    product = factory.SubFactory(ProductFactory)
    store = factory.SubFactory(StoreFactory)
    quantity = fuzzy.FuzzyInteger(0, 1000)
    min_stock = fuzzy.FuzzyInteger(0, 50)


class MovementFactory(factory.django.DjangoModelFactory):
    """Factory for creating Movement instances"""
    
    class Meta:
        model = Movement
    
    product = factory.SubFactory(ProductFactory)
    source_store = factory.SubFactory(StoreFactory)
    target_store = factory.SubFactory(StoreFactory)
    quantity = fuzzy.FuzzyInteger(1, 100)
    type = fuzzy.FuzzyChoice([choice[0] for choice in Movement.MOVEMENT_TYPES])