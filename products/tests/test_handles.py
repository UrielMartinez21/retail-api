"""
Unit tests for Product handles
"""

import json
from decimal import Decimal
from django.test import TestCase, RequestFactory
from unittest.mock import patch, MagicMock

from products.models import Store, Product, Inventory, Movement
from products.handles import (
    handle_get_products, handle_post_product, handle_get_product,
    handle_put_product, handle_delete_product
)
from products.tests.factories import StoreFactory, ProductFactory, InventoryFactory


class HandleGetProductsTest(TestCase):
    """Test cases for handle_get_products"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.store = StoreFactory()
        
        # Create products with inventory
        self.product1 = ProductFactory(name='Product 1', category='EL', price=Decimal('10.00'))
        self.product2 = ProductFactory(name='Product 2', category='FA', price=Decimal('20.00'))
        
        self.inventory1 = InventoryFactory(product=self.product1, store=self.store, quantity=100)
        self.inventory2 = InventoryFactory(product=self.product2, store=self.store, quantity=50)
    
    def test_handle_get_products_no_filters(self):
        """Test getting all products without filters"""
        request = self.factory.get('/products/')
        response = handle_get_products(request)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(len(data['data']), 2)
    
    def test_handle_get_products_with_category_filter(self):
        """Test getting products with category filter"""
        request = self.factory.get('/products/?category=EL')
        response = handle_get_products(request)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        # Should contain at least the electronics product
        product_categories = [product['category'] for product in data['data']]
        self.assertIn('EL', product_categories)
    
    def test_handle_get_products_with_price_filters(self):
        """Test getting products with price filters"""
        request = self.factory.get('/products/?min_price=15&max_price=25')
        response = handle_get_products(request)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
    
    def test_handle_get_products_with_store_filter(self):
        """Test getting products with store filter"""
        request = self.factory.get(f'/products/?store_id={self.store.id}')
        response = handle_get_products(request)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
    
    @patch('products.handles.logger')
    def test_handle_get_products_logging(self, mock_logger):
        """Test that handle_get_products logs properly"""
        request = self.factory.get('/products/')
        response = handle_get_products(request)
        
        # Verify logging was called
        mock_logger.info.assert_called()


class HandlePostProductTest(TestCase):
    """Test cases for handle_post_product"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.valid_product_data = {
            'name': 'Test Product',
            'description': 'A test product',
            'category': 'EL',
            'price': '29.99',
            'sku': 'TEST-001'
        }
    
    def test_handle_post_product_success(self):
        """Test successful product creation"""
        request = self.factory.post(
            '/products/',
            data=json.dumps(self.valid_product_data),
            content_type='application/json'
        )
        
        response = handle_post_product(request)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Verify product was created
        product = Product.objects.get(sku='TEST-001')
        self.assertEqual(product.name, 'Test Product')
        self.assertEqual(product.price, Decimal('29.99'))
    
    def test_handle_post_product_invalid_json(self):
        """Test product creation with invalid JSON"""
        request = self.factory.post(
            '/products/',
            data='invalid json',
            content_type='application/json'
        )
        
        response = handle_post_product(request)
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_handle_post_product_missing_fields(self):
        """Test product creation with missing required fields"""
        invalid_data = {
            'name': 'Test Product',
            # Missing other required fields
        }
        
        request = self.factory.post(
            '/products/',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        response = handle_post_product(request)
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_handle_post_product_duplicate_sku(self):
        """Test product creation with duplicate SKU"""
        # Create existing product
        existing_product = ProductFactory(sku='DUPLICATE-001')
        
        duplicate_data = self.valid_product_data.copy()
        duplicate_data['sku'] = 'DUPLICATE-001'
        
        request = self.factory.post(
            '/products/',
            data=json.dumps(duplicate_data),
            content_type='application/json'
        )
        
        response = handle_post_product(request)
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    @patch('products.handles.logger')
    def test_handle_post_product_logging(self, mock_logger):
        """Test that handle_post_product logs properly"""
        request = self.factory.post(
            '/products/',
            data=json.dumps(self.valid_product_data),
            content_type='application/json'
        )
        
        response = handle_post_product(request)
        
        # Verify logging was called
        mock_logger.info.assert_called()


class HandleGetProductTest(TestCase):
    """Test cases for handle_get_product"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.product = ProductFactory()
    
    def test_handle_get_product_success(self):
        """Test getting a specific product"""
        request = self.factory.get(f'/products/products/{self.product.id}/')
        response = handle_get_product(self.product.id)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['id'], self.product.id)
        self.assertEqual(data['data']['name'], self.product.name)
    
    def test_handle_get_product_not_found(self):
        """Test getting a non-existent product"""
        request = self.factory.get('/products/99999/')
        response = handle_get_product(99999)
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')


class HandlePutProductTest(TestCase):
    """Test cases for handle_put_product"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.product = ProductFactory(name='Original Name', price=Decimal('10.00'))
    
    def test_handle_put_product_success(self):
        """Test successful product update"""
        update_data = {
            'name': 'Updated Name',
            'price': '25.99'
        }
        
        request = self.factory.put(
            f'/products/products/{self.product.id}/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        response = handle_put_product(request, self.product.id)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Verify product was updated
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Updated Name')
        self.assertEqual(self.product.price, Decimal('25.99'))
    
    def test_handle_put_product_not_found(self):
        """Test updating a non-existent product"""
        update_data = {'name': 'Updated Name'}
        
        request = self.factory.put(
            '/products/99999/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        response = handle_put_product(request, 99999)
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_handle_put_product_invalid_json(self):
        """Test product update with invalid JSON"""
        request = self.factory.put(
            f'/products/products/{self.product.id}/',
            data='invalid json',
            content_type='application/json'
        )
        
        response = handle_put_product(request, self.product.id)
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_handle_put_product_partial_update(self):
        """Test partial product update"""
        update_data = {
            'name': 'Partially Updated Name'
            # Not updating price
        }
        
        original_price = self.product.price
        
        request = self.factory.put(
            f'/products/products/{self.product.id}/',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        response = handle_put_product(request, self.product.id)
        
        self.assertEqual(response.status_code, 200)
        
        # Verify product was partially updated
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Partially Updated Name')
        self.assertEqual(self.product.price, original_price)  # Should remain unchanged


class HandleDeleteProductTest(TestCase):
    """Test cases for handle_delete_product"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.product = ProductFactory()
    
    def test_handle_delete_product_success(self):
        """Test successful product deletion"""
        product_id = self.product.id
        
        request = self.factory.delete(f'/products/products/{product_id}/')
        response = handle_delete_product(product_id)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        # Verify product was deleted
        with self.assertRaises(Product.DoesNotExist):
            Product.objects.get(id=product_id)
    
    def test_handle_delete_product_not_found(self):
        """Test deleting a non-existent product"""
        request = self.factory.delete('/products/99999/')
        response = handle_delete_product(99999)
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_handle_delete_product_with_inventory(self):
        """Test deleting a product that has inventory"""
        # Create inventory for the product
        inventory = InventoryFactory(product=self.product)
        product_id = self.product.id
        
        request = self.factory.delete(f'/products/products/{product_id}/')
        response = handle_delete_product(product_id)
        
        # Product deletion should cascade and delete related inventory
        self.assertEqual(response.status_code, 200)
        
        # Verify product and inventory were deleted
        with self.assertRaises(Product.DoesNotExist):
            Product.objects.get(id=product_id)
        
        with self.assertRaises(Inventory.DoesNotExist):
            Inventory.objects.get(id=inventory.id)
    
    @patch('products.handles.logger')
    def test_handle_delete_product_logging(self, mock_logger):
        """Test that handle_delete_product logs properly"""
        product_id = self.product.id
        
        request = self.factory.delete(f'/products/products/{product_id}/')
        response = handle_delete_product(product_id)
        
        # Verify logging was called
        mock_logger.info.assert_called()