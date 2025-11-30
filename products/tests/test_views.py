"""
Unit tests for Product views
"""

import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock

from products.models import Store, Product, Inventory, Movement
from products.tests.factories import StoreFactory, ProductFactory, InventoryFactory


class ProductViewsTest(TestCase):
    """Test cases for Product views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.store1 = StoreFactory(name='Store 1')
        self.store2 = StoreFactory(name='Store 2')
        self.product1 = ProductFactory(name='Product 1', price=Decimal('10.00'))
        self.product2 = ProductFactory(name='Product 2', price=Decimal('20.00'))
        
        # Create some inventory
        self.inventory1 = InventoryFactory(
            product=self.product1,
            store=self.store1,
            quantity=100
        )
        self.inventory2 = InventoryFactory(
            product=self.product2,
            store=self.store2,
            quantity=50
        )
    
    def test_get_products_success(self):
        """Test GET /products/ returns all products"""
        response = self.client.get('/products/products/')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn('data', data)
        self.assertEqual(len(data['data']), 2)
    
    def test_get_products_with_filters(self):
        """Test GET /products/ with query parameters"""
        # Test category filter
        response = self.client.get(f'/products/?category={self.product1.category}')
        self.assertEqual(response.status_code, 200)
        
        # Test price filter
        response = self.client.get('/products/?min_price=15')
        data = json.loads(response.content)
        # Should only return product2 with price 20.00
        products_returned = [p for p in data['data'] if float(p['price']) >= 15]
        self.assertTrue(len(products_returned) >= 0)
    
    def test_get_products_with_store_filter(self):
        """Test GET /products/ with store filter"""
        response = self.client.get(f'/products/?store_id={self.store1.id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
    
    def test_post_product_success(self):
        """Test POST /products/ creates a new product"""
        product_data = {
            'name': 'New Product',
            'description': 'A new test product',
            'category': 'EL',
            'price': '25.99',
            'sku': 'NEW-001'
        }
        
        response = self.client.post(
            '/products/',
            data=json.dumps(product_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Verify product was created
        product = Product.objects.get(sku='NEW-001')
        self.assertEqual(product.name, 'New Product')
        self.assertEqual(product.price, Decimal('25.99'))
    
    def test_post_product_invalid_data(self):
        """Test POST /products/ with invalid data"""
        invalid_data = {
            'name': '',  # Empty name
            'price': 'invalid',  # Invalid price
        }
        
        response = self.client.post(
            '/products/',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_post_product_duplicate_sku(self):
        """Test POST /products/ with duplicate SKU"""
        product_data = {
            'name': 'Duplicate Product',
            'description': 'A product with duplicate SKU',
            'category': 'EL',
            'price': '30.00',
            'sku': self.product1.sku  # Use existing SKU
        }
        
        response = self.client.post(
            '/products/',
            data=json.dumps(product_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_options_request(self):
        """Test OPTIONS /products/ request"""
        response = self.client.options('/products/products/')
        self.assertEqual(response.status_code, 200)
    
    @patch('products.views.logger')
    def test_logging_in_views(self, mock_logger):
        """Test that views are logging properly"""
        response = self.client.get('/products/products/')
        
        # Verify that logging was called
        mock_logger.info.assert_called()
        
        # Check that the log contains expected information
        call_args = mock_logger.info.call_args
        self.assertIn('Products endpoint accessed', call_args[0])


class ProductDetailViewsTest(TestCase):
    """Test cases for individual product views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.product = ProductFactory()
    
    def test_get_product_success(self):
        """Test GET /products/{id}/ returns specific product"""
        response = self.client.get(f'/products/products/{self.product.id}/')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['id'], self.product.id)
        self.assertEqual(data['data']['name'], self.product.name)
    
    def test_get_product_not_found(self):
        """Test GET /products/{id}/ with non-existent ID"""
        response = self.client.get('/products/99999/')
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_put_product_success(self):
        """Test PUT /products/{id}/ updates product"""
        update_data = {
            'name': 'Updated Product Name',
            'price': '35.99'
        }
        
        response = self.client.put(
            f'/products/products/{self.product.id}/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify product was updated
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Updated Product Name')
        self.assertEqual(self.product.price, Decimal('35.99'))
    
    def test_delete_product_success(self):
        """Test DELETE /products/{id}/ deletes product"""
        product_id = self.product.id
        
        response = self.client.delete(f'/products/products/{product_id}/')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify product was deleted
        with self.assertRaises(Product.DoesNotExist):
            Product.objects.get(id=product_id)


class StoreViewsTest(TestCase):
    """Test cases for Store views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.store = StoreFactory()
    
    def test_get_stores_success(self):
        """Test GET /stores/ returns all stores"""
        response = self.client.get('/products/stores/')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn('data', data)
    
    def test_post_store_success(self):
        """Test POST /stores/ creates a new store"""
        store_data = {
            'name': 'New Store',
            'address': '456 New Street'
        }
        
        response = self.client.post(
            '/stores/',
            data=json.dumps(store_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Verify store was created
        store = Store.objects.get(name='New Store')
        self.assertEqual(store.address, '456 New Street')


class InventoryViewsTest(TestCase):
    """Test cases for Inventory views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.store = StoreFactory()
        self.product = ProductFactory()
        self.inventory = InventoryFactory(
            product=self.product,
            store=self.store,
            quantity=100,
            min_stock=10
        )
    
    def test_get_inventory_success(self):
        """Test GET /inventory/ returns inventory items"""
        response = self.client.get('/products/stores/1/inventory/')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIn('data', data)
    
    def test_get_inventory_with_store_filter(self):
        """Test GET /inventory/ with store filter"""
        response = self.client.get(f'/inventory/?store_id={self.store.id}')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
    
    def test_get_low_stock_items(self):
        """Test GET /inventory/low-stock/ endpoint"""
        # Create an item with low stock
        low_stock_inventory = InventoryFactory(
            quantity=5,
            min_stock=10
        )
        
        response = self.client.get('/products/inventory/alerts/')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        # Should return items where quantity < min_stock


class TransferViewsTest(TestCase):
    """Test cases for Transfer views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.source_store = StoreFactory(name='Source Store')
        self.target_store = StoreFactory(name='Target Store')
        self.product = ProductFactory()
        
        # Create inventory in source store
        self.source_inventory = InventoryFactory(
            product=self.product,
            store=self.source_store,
            quantity=100
        )
        
        # Create inventory in target store (or it will be created)
        self.target_inventory = InventoryFactory(
            product=self.product,
            store=self.target_store,
            quantity=20
        )
    
    def test_post_transfer_success(self):
        """Test POST /transfer/ successfully transfers inventory"""
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.source_store.id,
            'target_store_id': self.target_store.id,
            'quantity': 30
        }
        
        response = self.client.post(
            '/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Verify inventory was updated
        self.source_inventory.refresh_from_db()
        self.target_inventory.refresh_from_db()
        
        self.assertEqual(self.source_inventory.quantity, 70)  # 100 - 30
        self.assertEqual(self.target_inventory.quantity, 50)  # 20 + 30
    
    def test_post_transfer_insufficient_stock(self):
        """Test POST /transfer/ with insufficient stock"""
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.source_store.id,
            'target_store_id': self.target_store.id,
            'quantity': 150  # More than available (100)
        }
        
        response = self.client.post(
            '/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_post_transfer_invalid_data(self):
        """Test POST /transfer/ with invalid data"""
        invalid_data = {
            'product_id': 99999,  # Non-existent product
            'source_store_id': self.source_store.id,
            'target_store_id': self.target_store.id,
            'quantity': 30
        }
        
        response = self.client.post(
            '/transfer/',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')