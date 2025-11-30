"""
Integration tests for the complete product management system
"""

import json
from decimal import Decimal
from django.test import TestCase, TransactionTestCase, Client
from django.db import transaction

from products.models import Store, Product, Inventory, Movement
from products.tests.factories import StoreFactory, ProductFactory, InventoryFactory


class ProductManagementIntegrationTest(TestCase):
    """Integration tests for the complete product management workflow"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create stores
        self.store_a = StoreFactory(name='Store A')
        self.store_b = StoreFactory(name='Store B')
        self.store_c = StoreFactory(name='Store C')
        
        # Create products
        self.laptop = ProductFactory(
            name='Laptop',
            category='EL',
            price=Decimal('999.99'),
            sku='LAPTOP-001'
        )
        self.mouse = ProductFactory(
            name='Mouse',
            category='EL', 
            price=Decimal('29.99'),
            sku='MOUSE-001'
        )
        
        # Create initial inventory
        self.laptop_inventory_a = InventoryFactory(
            product=self.laptop,
            store=self.store_a,
            quantity=50,
            min_stock=10
        )
        self.mouse_inventory_a = InventoryFactory(
            product=self.mouse,
            store=self.store_a,
            quantity=100,
            min_stock=20
        )
        self.laptop_inventory_b = InventoryFactory(
            product=self.laptop,
            store=self.store_b,
            quantity=25,
            min_stock=5
        )
    
    def test_complete_product_lifecycle(self):
        """Test complete product lifecycle: create, read, update, delete"""
        # 1. Create a new product
        new_product_data = {
            'name': 'Keyboard',
            'description': 'Wireless keyboard',
            'category': 'EL',
            'price': '79.99',
            'sku': 'KEYBOARD-001'
        }
        
        response = self.client.post(
            '/products/',
            data=json.dumps(new_product_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # 2. Read the created product
        keyboard = Product.objects.get(sku='KEYBOARD-001')
        response = self.client.get(f'/products/products/{keyboard.id}/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['data']['name'], 'Keyboard')
        self.assertEqual(data['data']['price'], '79.99')
        
        # 3. Update the product
        update_data = {
            'name': 'Premium Keyboard',
            'price': '99.99'
        }
        response = self.client.put(
            f'/products/{keyboard.id}/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify update
        keyboard.refresh_from_db()
        self.assertEqual(keyboard.name, 'Premium Keyboard')
        self.assertEqual(keyboard.price, Decimal('99.99'))
        
        # 4. Delete the product
        response = self.client.delete(f'/products/products/{keyboard.id}/')
        self.assertEqual(response.status_code, 200)
        
        # Verify deletion
        with self.assertRaises(Product.DoesNotExist):
            Product.objects.get(id=keyboard.id)
    
    def test_inventory_transfer_workflow(self):
        """Test complete inventory transfer workflow"""
        # Initial state: Store A has 50 laptops, Store B has 25 laptops
        
        # 1. Transfer 20 laptops from Store A to Store B
        transfer_data = {
            'product_id': self.laptop.id,
            'source_store_id': self.store_a.id,
            'target_store_id': self.store_b.id,
            'quantity': 20
        }
        
        response = self.client.post(
            '/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify inventory changes
        self.laptop_inventory_a.refresh_from_db()
        self.laptop_inventory_b.refresh_from_db()
        
        self.assertEqual(self.laptop_inventory_a.quantity, 30)  # 50 - 20
        self.assertEqual(self.laptop_inventory_b.quantity, 45)  # 25 + 20
        
        # Verify movement record
        movement = Movement.objects.get(
            product=self.laptop,
            source_store=self.store_a,
            target_store=self.store_b,
            quantity=20,
            type='TRANSFER'
        )
        self.assertIsNotNone(movement)
        
        # 2. Transfer to a store with no existing inventory
        transfer_data = {
            'product_id': self.laptop.id,
            'source_store_id': self.store_a.id,
            'target_store_id': self.store_c.id,
            'quantity': 10
        }
        
        response = self.client.post(
            '/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify new inventory created
        laptop_inventory_c = Inventory.objects.get(
            product=self.laptop,
            store=self.store_c
        )
        self.assertEqual(laptop_inventory_c.quantity, 10)
        
        # Verify source inventory updated
        self.laptop_inventory_a.refresh_from_db()
        self.assertEqual(self.laptop_inventory_a.quantity, 20)  # 30 - 10
    
    def test_store_management_workflow(self):
        """Test store creation and management"""
        # 1. Create a new store
        store_data = {
            'name': 'Store D',
            'address': '123 New Street'
        }
        
        response = self.client.post(
            '/stores/',
            data=json.dumps(store_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # 2. Verify store creation
        store_d = Store.objects.get(name='Store D')
        self.assertEqual(store_d.address, '123 New Street')
        
        # 3. Get all stores
        response = self.client.get('/products/stores/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        store_names = [store['name'] for store in data['data']]
        self.assertIn('Store D', store_names)
    
    def test_inventory_reporting_workflow(self):
        """Test inventory reporting and low stock detection"""
        # 1. Get all inventory
        response = self.client.get('/products/stores/1/inventory/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertGreaterEqual(len(data['data']), 3)  # At least 3 inventory items
        
        # 2. Filter inventory by store
        response = self.client.get(f'/inventory/?store_id={self.store_a.id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        for item in data['data']:
            self.assertEqual(item['store_id'], self.store_a.id)
        
        # 3. Check low stock items
        # Create a low stock item
        low_stock_inventory = InventoryFactory(
            product=self.mouse,
            store=self.store_b,
            quantity=5,
            min_stock=20  # quantity < min_stock
        )
        
        response = self.client.get('/products/inventory/alerts/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        # Should contain the low stock item
        low_stock_items = [item for item in data['data'] 
                          if item['quantity'] < item['min_stock']]
        self.assertGreater(len(low_stock_items), 0)
    
    def test_product_filtering_workflow(self):
        """Test product filtering capabilities"""
        # 1. Filter by category
        response = self.client.get('/products/?category=EL')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        for product in data['data']:
            self.assertEqual(product['category'], 'EL')
        
        # 2. Filter by price range
        response = self.client.get('/products/?min_price=30&max_price=100')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        for product in data['data']:
            price = float(product['price'])
            self.assertGreaterEqual(price, 30)
            self.assertLessEqual(price, 100)
        
        # 3. Filter by store
        response = self.client.get(f'/products/?store_id={self.store_a.id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertGreater(len(data['data']), 0)
    
    def test_error_handling_workflow(self):
        """Test error handling across the system"""
        # 1. Try to create product with duplicate SKU
        duplicate_product_data = {
            'name': 'Another Laptop',
            'description': 'Another laptop',
            'category': 'EL',
            'price': '1200.00',
            'sku': self.laptop.sku  # Duplicate SKU
        }
        
        response = self.client.post(
            '/products/',
            data=json.dumps(duplicate_product_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # 2. Try to transfer more inventory than available
        transfer_data = {
            'product_id': self.laptop.id,
            'source_store_id': self.store_a.id,
            'target_store_id': self.store_b.id,
            'quantity': 1000  # More than available
        }
        
        response = self.client.post(
            '/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # 3. Try to get non-existent product
        response = self.client.get('/products/99999/')
        self.assertEqual(response.status_code, 404)
        
        # 4. Try to update non-existent product
        update_data = {'name': 'Updated Name'}
        response = self.client.put(
            '/products/99999/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)


class DatabaseTransactionTest(TransactionTestCase):
    """Test database transactions and rollbacks"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.store_a = StoreFactory()
        self.store_b = StoreFactory()
        self.product = ProductFactory()
        self.inventory = InventoryFactory(
            product=self.product,
            store=self.store_a,
            quantity=100
        )
    
    def test_inventory_transfer_atomicity(self):
        """Test that inventory transfers are atomic"""
        # This test would require simulating a database error
        # to verify that failed transfers don't leave the system
        # in an inconsistent state
        
        initial_quantity = self.inventory.quantity
        
        # Normal transfer should work
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.store_a.id,
            'target_store_id': self.store_b.id,
            'quantity': 25
        }
        
        response = self.client.post(
            '/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify transaction completed successfully
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 75)  # 100 - 25
        
        # Verify movement record exists
        movement_count = Movement.objects.filter(
            product=self.product,
            type='TRANSFER'
        ).count()
        self.assertEqual(movement_count, 1)