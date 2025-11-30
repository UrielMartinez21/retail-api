"""
Unit tests for Product helpers
"""

import json
from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.http import JsonResponse
from unittest.mock import patch, MagicMock

from products.models import Store, Product, Inventory, Movement
from products.helpers import (
    get_query_params, build_response, fetch_product_and_stores,
    perform_inventory_transfer, validate_request_body, validate_source_inventory
)
from products.tests.factories import StoreFactory, ProductFactory, InventoryFactory


class GetQueryParamsTest(TestCase):
    """Test cases for get_query_params helper"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
    
    def test_get_query_params_empty(self):
        """Test get_query_params with no parameters"""
        request = self.factory.get('/products/')
        params = get_query_params(request)
        
        expected = {
            'category': None,
            'min_price': None,
            'max_price': None,
            'in_stock': None,
            'page': 1,
            'page_size': 10
        }
        self.assertEqual(params, expected)
    
    def test_get_query_params_with_values(self):
        """Test get_query_params with various parameters"""
        request = self.factory.get('/products/?category=EL&min_price=10.00&max_price=50.00&in_stock=true&page=2&page_size=5')
        params = get_query_params(request)
        
        expected = {
            'category': 'EL',
            'min_price': '10.00',
            'max_price': '50.00',
            'in_stock': 'true',
            'page': '2',
            'page_size': '5'
        }
        self.assertEqual(params, expected)
    
    def test_get_query_params_partial(self):
        """Test get_query_params with some parameters"""
        request = self.factory.get('/products/?category=FA&page=3')
        params = get_query_params(request)
        
        self.assertEqual(params['category'], 'FA')
        self.assertEqual(params['page'], '3')
        self.assertIsNone(params['min_price'])
        self.assertIsNone(params['max_price'])
        self.assertIsNone(params['in_stock'])


class BuildResponseTest(TestCase):
    """Test cases for build_response helper"""
    
    def test_build_response_success_with_data(self):
        """Test build_response with success status and data"""
        data = {'products': [{'id': 1, 'name': 'Test Product'}]}
        response = build_response('success', 200, data)
        
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 200)
        
        content = json.loads(response.content)
        self.assertEqual(content['status'], 'success')
        self.assertEqual(content['data'], data)
    
    def test_build_response_error_with_message(self):
        """Test build_response with error status and message"""
        message = 'Product not found'
        response = build_response('error', 404, message=message)
        
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 404)
        
        content = json.loads(response.content)
        self.assertEqual(content['status'], 'error')
        self.assertEqual(content['message'], message)
    
    def test_build_response_no_data_no_message(self):
        """Test build_response without data or message"""
        response = build_response('success', 200)
        
        self.assertEqual(response.status_code, 200)
        
        content = json.loads(response.content)
        self.assertEqual(content['status'], 'success')
        self.assertEqual(content['message'], '')
        self.assertIsNone(content['data'])


class FetchProductAndStoresTest(TestCase):
    """Test cases for fetch_product_and_stores helper"""
    
    def setUp(self):
        """Set up test data"""
        self.product = ProductFactory()
        self.source_store = StoreFactory()
        self.target_store = StoreFactory()
    
    def test_fetch_product_and_stores_success(self):
        """Test successful fetch of product and stores"""
        result = fetch_product_and_stores({"product_id": self.product.id, "source_store_id": self.source_store.id, "target_store_id": self.target_store.id
        })
        
        self.assertEqual(result[0], self.product)
        self.assertEqual(result[1], self.source_store)
        self.assertEqual(result[2], self.target_store)
    
    def test_fetch_product_and_stores_invalid_product(self):
        """Test fetch with invalid product ID"""
        with self.assertRaises(Product.DoesNotExist):
            fetch_product_and_stores({"product_id": 99999, "source_store_id": # Invalid product ID
                self.source_store.id, "target_store_id": self.target_store.id
            })
    
    def test_fetch_product_and_stores_invalid_source_store(self):
        """Test fetch with invalid source store ID"""
        with self.assertRaises(Store.DoesNotExist):
            fetch_product_and_stores({"product_id": self.product.id, "source_store_id": 99999, "target_store_id": # Invalid store ID
                self.target_store.id
            })
    
    def test_fetch_product_and_stores_invalid_target_store(self):
        """Test fetch with invalid target store ID"""
        with self.assertRaises(Store.DoesNotExist):
            fetch_product_and_stores({"product_id": self.product.id, "source_store_id": self.source_store.id, "target_store_id": 99999  # Invalid store ID
            })


class ValidateRequestBodyTest(TestCase):
    """Test cases for validate_request_body helper"""
    
    def test_validate_request_body_success(self):
        """Test successful request body validation"""
        data = {
            'product_id': 1,
            'source_store_id': 2,
            'target_store_id': 3,
            'quantity': 50
        }
        
        # Should not raise any exception
        validate_request_body(data)
    
    def test_validate_request_body_missing_fields(self):
        """Test validation with missing required fields"""
        data = {
            'product_id': 1,
            # Missing other required fields
        }
        
        with self.assertRaises(ValueError):
            validate_request_body(data)
    
    def test_validate_request_body_invalid_quantity(self):
        """Test validation with invalid quantity"""
        data = {
            'product_id': 1,
            'source_store_id': 2,
            'target_store_id': 3,
            'quantity': 0  # Invalid quantity
        }
        
        with self.assertRaises(ValueError):
            validate_request_body(data)
    
    def test_validate_request_body_negative_quantity(self):
        """Test validation with negative quantity"""
        data = {
            'product_id': 1,
            'source_store_id': 2,
            'target_store_id': 3,
            'quantity': -10  # Negative quantity
        }
        
        with self.assertRaises(ValueError):
            validate_request_body(data)


class ValidateSourceInventoryTest(TestCase):
    """Test cases for validate_source_inventory helper"""
    
    def setUp(self):
        """Set up test data"""
        self.product = ProductFactory()
        self.source_store = StoreFactory()
        self.source_inventory = InventoryFactory(
            product=self.product,
            store=self.source_store,
            quantity=100
        )
    
    def test_validate_source_inventory_success(self):
        """Test successful source inventory validation"""
        # Should not raise any exception
        validate_source_inventory(self.product, self.source_store, 50)
    
    def test_validate_source_inventory_insufficient_stock(self):
        """Test validation with insufficient stock"""
        with self.assertRaises(ValueError):
            validate_source_inventory(self.product, self.source_store, 150)  # More than available
    
    def test_validate_source_inventory_exact_quantity(self):
        """Test validation with exact available quantity"""
        # Should not raise any exception
        validate_source_inventory(self.product, self.source_store, 100)


class PerformInventoryTransferTest(TestCase):
    """Test cases for perform_inventory_transfer helper"""
    
    def setUp(self):
        """Set up test data"""
        self.product = ProductFactory()
        self.source_store = StoreFactory()
        self.target_store = StoreFactory()
        
        self.source_inventory = InventoryFactory(
            product=self.product,
            store=self.source_store,
            quantity=100
        )
        
        self.target_inventory = InventoryFactory(
            product=self.product,
            store=self.target_store,
            quantity=20
        )
    
    def test_perform_inventory_transfer_success(self):
        """Test successful inventory transfer"""
        transfer_quantity = 30
        
        perform_inventory_transfer(self.product, self.source_store, self.target_store, transfer_quantity
        , self.source_inventory)
        
        # Refresh from database
        self.source_inventory.refresh_from_db()
        self.target_inventory.refresh_from_db()
        
        # Verify quantities updated
        self.assertEqual(self.source_inventory.quantity, 70)  # 100 - 30
        self.assertEqual(self.target_inventory.quantity, 50)  # 20 + 30
        
        # Verify movement record created
        movement = Movement.objects.get(
            product=self.product,
            source_store=self.source_store,
            target_store=self.target_store,
            quantity=transfer_quantity,
            type='TRANSFER'
        )
        self.assertIsNotNone(movement)
    
    def test_perform_inventory_transfer_new_target_inventory(self):
        """Test transfer to store with no existing inventory"""
        new_target_store = StoreFactory()
        transfer_quantity = 25
        
        perform_inventory_transfer(self.product, self.source_store, new_target_store, transfer_quantity
        , self.source_inventory)
        
        # Verify source inventory updated
        self.source_inventory.refresh_from_db()
        self.assertEqual(self.source_inventory.quantity, 75)  # 100 - 25
        
        # Verify new target inventory created
        new_target_inventory = Inventory.objects.get(
            product=self.product,
            store=new_target_store
        )
        self.assertEqual(new_target_inventory.quantity, 25)
    
    @patch('products.helpers.logger')
    def test_perform_inventory_transfer_logging(self, mock_logger):
        """Test that inventory transfer logs properly"""
        transfer_quantity = 15
        
        perform_inventory_transfer(self.product, self.source_store, self.target_store, transfer_quantity
        , self.source_inventory)
        
        # Verify logging was called
        mock_logger.info.assert_called()
    
    def test_perform_inventory_transfer_atomic(self):
        """Test that inventory transfer is atomic (all or nothing)"""
        # This test would require simulating a database error
        # to verify that the transaction rolls back properly
        pass  # Would need more complex setup to test properly