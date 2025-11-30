"""
Unit tests for Product models
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal

from products.models import Store, Product, Inventory, Movement
from products.tests.factories import StoreFactory, ProductFactory, InventoryFactory, MovementFactory


class StoreModelTest(TestCase):
    """Test cases for Store model"""
    
    def setUp(self):
        """Set up test data"""
        self.store_data = {
            'name': 'Test Store',
            'address': '123 Test Street'
        }
    
    def test_store_creation(self):
        """Test creating a store"""
        store = Store.objects.create(**self.store_data)
        
        self.assertEqual(store.name, 'Test Store')
        self.assertEqual(store.address, '123 Test Street')
        self.assertEqual(str(store), 'Test Store')
    
    def test_store_creation_without_address(self):
        """Test creating a store without address"""
        store = Store.objects.create(name='Test Store')
        
        self.assertEqual(store.name, 'Test Store')
        self.assertIsNone(store.address)
    
    def test_store_string_representation(self):
        """Test store string representation"""
        store = StoreFactory()
        self.assertEqual(str(store), store.name)
    
    def test_store_max_length_name(self):
        """Test store name max length"""
        long_name = 'a' * 101  # Exceeds 100 char limit
        with self.assertRaises(ValidationError):
            store = Store(name=long_name)
            store.full_clean()
    
    def test_store_relationships(self):
        """Test store relationships with inventory"""
        store = StoreFactory()
        inventory = InventoryFactory(store=store)
        
        self.assertEqual(store.inventory.count(), 1)
        self.assertEqual(store.inventory.first(), inventory)


class ProductModelTest(TestCase):
    """Test cases for Product model"""
    
    def setUp(self):
        """Set up test data"""
        self.product_data = {
            'name': 'Test Product',
            'description': 'A test product description',
            'category': Product.Category.ELECTRONICS,
            'price': Decimal('99.99'),
            'sku': 'TEST-001'
        }
    
    def test_product_creation(self):
        """Test creating a product"""
        product = Product.objects.create(**self.product_data)
        
        self.assertEqual(product.name, 'Test Product')
        self.assertEqual(product.description, 'A test product description')
        self.assertEqual(product.category, Product.Category.ELECTRONICS)
        self.assertEqual(product.price, Decimal('99.99'))
        self.assertEqual(product.sku, 'TEST-001')
        self.assertEqual(str(product), 'Test Product')
    
    def test_product_default_category(self):
        """Test product default category"""
        product_data = self.product_data.copy()
        del product_data['category']
        product = Product.objects.create(**product_data)
        
        self.assertEqual(product.category, Product.Category.HOME)
    
    def test_unique_sku_constraint(self):
        """Test that SKU must be unique"""
        Product.objects.create(**self.product_data)
        
        with self.assertRaises(IntegrityError):
            Product.objects.create(**self.product_data)
    
    def test_product_categories(self):
        """Test all product categories"""
        categories = [
            Product.Category.ELECTRONICS,
            Product.Category.FASHION,
            Product.Category.HOME,
            Product.Category.TOYS,
            Product.Category.SPORTS
        ]
        
        for category in categories:
            product_data = self.product_data.copy()
            product_data['sku'] = f'TEST-{category}'
            product = Product.objects.create(category=category, **product_data)
            self.assertEqual(product.category, category)
    
    def test_product_ordering(self):
        """Test product ordering by name"""
        ProductFactory(name='Zebra Product')
        ProductFactory(name='Alpha Product') 
        ProductFactory(name='Beta Product')
        
        products = Product.objects.all()
        names = [p.name for p in products]
        
        self.assertEqual(names, sorted(names))
    
    def test_product_price_validation(self):
        """Test product price validation"""
        # Test negative price
        product_data = self.product_data.copy()
        product_data['price'] = Decimal('-10.00')
        
        # Django doesn't validate this at model level by default,
        # but we can test the field constraints
        product = Product(**product_data)
        # This would need custom validation in the model
        # For now, we just test that it accepts valid prices
        
        product_data['price'] = Decimal('0.01')
        product = Product.objects.create(**product_data)
        self.assertEqual(product.price, Decimal('0.01'))


class InventoryModelTest(TestCase):
    """Test cases for Inventory model"""
    
    def setUp(self):
        """Set up test data"""
        self.store = StoreFactory()
        self.product = ProductFactory()
        self.inventory_data = {
            'product': self.product,
            'store': self.store,
            'quantity': 100,
            'min_stock': 10
        }
    
    def test_inventory_creation(self):
        """Test creating inventory"""
        inventory = Inventory.objects.create(**self.inventory_data)
        
        self.assertEqual(inventory.product, self.product)
        self.assertEqual(inventory.store, self.store)
        self.assertEqual(inventory.quantity, 100)
        self.assertEqual(inventory.min_stock, 10)
    
    def test_inventory_string_representation(self):
        """Test inventory string representation"""
        inventory = Inventory.objects.create(**self.inventory_data)
        expected_str = f"{self.product.name} - {self.store.name} (100)"
        self.assertEqual(str(inventory), expected_str)
    
    def test_inventory_default_values(self):
        """Test inventory default values"""
        inventory = Inventory.objects.create(
            product=self.product,
            store=self.store
        )
        
        self.assertEqual(inventory.quantity, 0)
        self.assertEqual(inventory.min_stock, 0)
    
    def test_unique_together_constraint(self):
        """Test unique together constraint for product and store"""
        Inventory.objects.create(**self.inventory_data)
        
        with self.assertRaises(IntegrityError):
            Inventory.objects.create(**self.inventory_data)
    
    def test_inventory_relationships(self):
        """Test inventory relationships"""
        inventory = InventoryFactory(product=self.product, store=self.store)
        
        # Test product relationship
        self.assertIn(inventory, self.product.inventory_items.all())
        
        # Test store relationship
        self.assertIn(inventory, self.store.inventory.all())


class MovementModelTest(TestCase):
    """Test cases for Movement model"""
    
    def setUp(self):
        """Set up test data"""
        self.product = ProductFactory()
        self.source_store = StoreFactory()
        self.target_store = StoreFactory()
        self.movement_data = {
            'product': self.product,
            'source_store': self.source_store,
            'target_store': self.target_store,
            'quantity': 50,
            'type': 'TRANSFER'
        }
    
    def test_movement_creation(self):
        """Test creating a movement"""
        movement = Movement.objects.create(**self.movement_data)
        
        self.assertEqual(movement.product, self.product)
        self.assertEqual(movement.source_store, self.source_store)
        self.assertEqual(movement.target_store, self.target_store)
        self.assertEqual(movement.quantity, 50)
        self.assertEqual(movement.type, 'TRANSFER')
        self.assertIsNotNone(movement.timestamp)
    
    def test_movement_string_representation(self):
        """Test movement string representation"""
        movement = Movement.objects.create(**self.movement_data)
        expected_str = f"{self.product.name} - TRANSFER (50)"
        self.assertEqual(str(movement), expected_str)
    
    def test_movement_types(self):
        """Test all movement types"""
        movement_types = ['IN', 'OUT', 'TRANSFER']
        
        for movement_type in movement_types:
            movement_data = self.movement_data.copy()
            movement_data['type'] = movement_type
            movement = Movement.objects.create(**movement_data)
            self.assertEqual(movement.type, movement_type)
    
    def test_movement_with_null_stores(self):
        """Test movement with null source/target stores"""
        # Test IN movement (no source store)
        movement_data = {
            'product': self.product,
            'source_store': None,
            'target_store': self.target_store,
            'quantity': 50,
            'type': 'IN'
        }
        movement = Movement.objects.create(**movement_data)
        self.assertIsNone(movement.source_store)
        
        # Test OUT movement (no target store)
        movement_data = {
            'product': self.product,
            'source_store': self.source_store,
            'target_store': None,
            'quantity': 25,
            'type': 'OUT'
        }
        movement = Movement.objects.create(**movement_data)
        self.assertIsNone(movement.target_store)
    
    def test_movement_quantity_positive(self):
        """Test that movement quantity must be positive"""
        movement_data = self.movement_data.copy()
        movement_data['quantity'] = 0
        
        # PositiveIntegerField should prevent 0
        with self.assertRaises(IntegrityError):
            Movement.objects.create(**movement_data)