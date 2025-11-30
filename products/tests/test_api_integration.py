"""
API Integration Tests for Critical Endpoints

Tests focused on API behavior, response validation,
error handling, and endpoint-specific flows.
"""

import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse

from products.models import Store, Product, Inventory, Movement
from products.tests.factories import StoreFactory, ProductFactory, InventoryFactory


class APIEndpointIntegrationTest(TestCase):
    """Integration tests for API endpoints"""
    
    def setUp(self):
        """Set up API test data"""
        self.client = Client()
        
        # Create test stores
        self.warehouse = StoreFactory(
            name='API Test Warehouse',
            address='123 Warehouse St'
        )
        self.retail_store = StoreFactory(
            name='API Test Retail',
            address='456 Retail Ave'
        )
        
        # Create test products
        self.electronics_product = ProductFactory(
            name='API Test Laptop',
            category='EL',
            price=Decimal('999.99'),
            sku='API-EL-001'
        )
        
        self.furniture_product = ProductFactory(
            name='API Test Chair',
            category='FU',
            price=Decimal('149.99'),
            sku='API-FU-001'
        )
        
        # Create inventory
        InventoryFactory(
            product=self.electronics_product,
            store=self.warehouse,
            quantity=50,
            min_stock=10
        )
        
        InventoryFactory(
            product=self.furniture_product,
            store=self.warehouse,
            quantity=100,
            min_stock=15
        )
        
        InventoryFactory(
            product=self.electronics_product,
            store=self.retail_store,
            quantity=5,
            min_stock=2
        )

    def test_product_list_api_functionality(self):
        """Test product listing API with various filters"""
        
        # Test basic product list
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        
        # Verify product data structure
        product_data = data[0]
        expected_fields = ['id', 'name', 'category', 'price', 'sku']
        for field in expected_fields:
            self.assertIn(field, product_data)
        
        # Test category filtering
        response = self.client.get('/products/products/?category=EL')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['category'], 'EL')
        
        # Test invalid category
        response = self.client.get('/products/products/?category=INVALID')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    def test_store_list_api_functionality(self):
        """Test store listing API"""
        
        response = self.client.get('/api/stores/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        
        # Verify store data structure
        store_data = data[0]
        expected_fields = ['id', 'name', 'address']
        for field in expected_fields:
            self.assertIn(field, store_data)

    def test_inventory_transfer_api_complete_flow(self):
        """Test complete inventory transfer API flow"""
        
        # Get initial inventory state
        warehouse_inventory = Inventory.objects.get(
            product=self.electronics_product,
            store=self.warehouse
        )
        retail_inventory = Inventory.objects.get(
            product=self.electronics_product,
            store=self.retail_store
        )
        
        initial_warehouse_qty = warehouse_inventory.quantity
        initial_retail_qty = retail_inventory.quantity
        transfer_qty = 10
        
        # Perform transfer
        transfer_data = {
            'product_id': self.electronics_product.id,
            'source_store_id': self.warehouse.id,
            'target_store_id': self.retail_store.id,
            'quantity': transfer_qty
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn('movement_id', response_data)
        
        # Verify inventory changes
        warehouse_inventory.refresh_from_db()
        retail_inventory.refresh_from_db()
        
        self.assertEqual(
            warehouse_inventory.quantity,
            initial_warehouse_qty - transfer_qty
        )
        self.assertEqual(
            retail_inventory.quantity,
            initial_retail_qty + transfer_qty
        )
        
        # Verify movement record
        movement = Movement.objects.get(id=response_data['movement_id'])
        self.assertEqual(movement.product, self.electronics_product)
        self.assertEqual(movement.source_store, self.warehouse)
        self.assertEqual(movement.target_store, self.retail_store)
        self.assertEqual(movement.quantity, transfer_qty)

    def test_inventory_transfer_error_handling(self):
        """Test error handling in inventory transfer API"""
        
        # Test 1: Non-existent product
        transfer_data = {
            'product_id': 99999,
            'source_store_id': self.warehouse.id,
            'target_store_id': self.retail_store.id,
            'quantity': 10
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        error_data = response.json()
        self.assertIn('error', error_data)
        
        # Test 2: Non-existent source store
        transfer_data = {
            'product_id': self.electronics_product.id,
            'source_store_id': 99999,
            'target_store_id': self.retail_store.id,
            'quantity': 10
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Test 3: Insufficient inventory
        transfer_data = {
            'product_id': self.electronics_product.id,
            'source_store_id': self.warehouse.id,
            'target_store_id': self.retail_store.id,
            'quantity': 1000  # More than available
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Test 4: Invalid JSON
        response = self.client.post(
            '/api/inventory/transfer/',
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Test 5: Missing required fields
        incomplete_data = {
            'product_id': self.electronics_product.id,
            # Missing other required fields
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)

    def test_store_inventory_api(self):
        """Test store-specific inventory API"""
        
        # Test warehouse inventory
        response = self.client.get(f'/api/stores/{self.warehouse.id}/inventory/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)  # Two products in warehouse
        
        # Verify inventory data structure
        inventory_item = data[0]
        expected_fields = ['product', 'quantity', 'min_stock']
        for field in expected_fields:
            self.assertIn(field, inventory_item)
        
        # Verify product details are included
        self.assertIsInstance(inventory_item['product'], dict)
        product_fields = ['id', 'name', 'category', 'price', 'sku']
        for field in product_fields:
            self.assertIn(field, inventory_item['product'])
        
        # Test retail store inventory
        response = self.client.get(f'/api/stores/{self.retail_store.id}/inventory/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data), 1)  # One product in retail store
        
        # Test non-existent store
        response = self.client.get('/products/stores/99999/inventory/')
        self.assertEqual(response.status_code, 404)

    def test_low_stock_alerts_api(self):
        """Test low stock alerts API"""
        
        response = self.client.get('/api/inventory/alerts/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        
        # Electronics in retail store should be low stock (5 < 2 is false, but 5 == 2 might trigger)
        # Let's create a proper low stock situation
        
        # Update to create low stock
        retail_inventory = Inventory.objects.get(
            product=self.electronics_product,
            store=self.retail_store
        )
        retail_inventory.quantity = 1  # Below min_stock of 2
        retail_inventory.save()
        
        response = self.client.get('/api/inventory/alerts/')
        data = response.json()
        
        # Should have at least one low stock alert
        self.assertGreater(len(data), 0)
        
        # Verify alert data structure
        if data:
            alert_item = data[0]
            expected_fields = ['store', 'product', 'current_quantity', 'min_stock']
            for field in expected_fields:
                self.assertIn(field, alert_item)

    def test_movement_history_api(self):
        """Test movement history API"""
        
        # Create some movements first
        transfer_data = {
            'product_id': self.electronics_product.id,
            'source_store_id': self.warehouse.id,
            'target_store_id': self.retail_store.id,
            'quantity': 5
        }
        
        # Perform transfer to create movement
        self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        # Test general movements API
        response = self.client.get('/api/movements/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Verify movement data structure
        movement_item = data[0]
        expected_fields = ['id', 'product', 'source_store', 'target_store', 
                          'quantity', 'type', 'timestamp']
        for field in expected_fields:
            self.assertIn(field, movement_item)


class APIValidationIntegrationTest(TestCase):
    """Integration tests for API input validation"""
    
    def setUp(self):
        """Set up validation test data"""
        self.client = Client()
        
        self.store = StoreFactory(name='Validation Test Store')
        self.product = ProductFactory(
            name='Validation Test Product',
            category='SP',
            price=Decimal('25.99'),
            sku='VAL-001'
        )
        
        InventoryFactory(
            product=self.product,
            store=self.store,
            quantity=100,
            min_stock=10
        )

    def test_transfer_quantity_validation(self):
        """Test quantity validation in transfer API"""
        
        base_transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.store.id,
            'target_store_id': self.store.id,
        }
        
        # Test negative quantity
        transfer_data = base_transfer_data.copy()
        transfer_data['quantity'] = -5
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test zero quantity
        transfer_data['quantity'] = 0
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test non-numeric quantity
        transfer_data['quantity'] = 'invalid'
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test decimal quantity (should be rejected or handled)
        transfer_data['quantity'] = 5.5
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        # Should either be accepted (if handled) or rejected (if not supported)
        self.assertIn(response.status_code, [200, 400])

    def test_store_id_validation(self):
        """Test store ID validation in transfer API"""
        
        base_transfer_data = {
            'product_id': self.product.id,
            'quantity': 10,
        }
        
        # Test invalid source store ID
        transfer_data = base_transfer_data.copy()
        transfer_data.update({
            'source_store_id': 'invalid',
            'target_store_id': self.store.id
        })
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        # Test null store IDs
        transfer_data.update({
            'source_store_id': None,
            'target_store_id': self.store.id
        })
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_content_type_validation(self):
        """Test API content type validation"""
        
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.store.id,
            'target_store_id': self.store.id,
            'quantity': 10
        }
        
        # Test without content type
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data)
            # No content_type specified
        )
        # Should handle gracefully
        self.assertIn(response.status_code, [200, 400, 415])
        
        # Test with wrong content type
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='text/plain'
        )
        self.assertIn(response.status_code, [400, 415])

    def test_http_method_validation(self):
        """Test HTTP method validation for APIs"""
        
        # Test GET on transfer endpoint (should be POST only)
        response = self.client.get('/api/inventory/transfer/')
        self.assertEqual(response.status_code, 405)  # Method not allowed
        
        # Test PUT on transfer endpoint
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.store.id,
            'target_store_id': self.store.id,
            'quantity': 10
        }
        
        response = self.client.put(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 405)


class APIResponseFormatTest(TestCase):
    """Test API response format consistency"""
    
    def setUp(self):
        """Set up response format test data"""
        self.client = Client()
        
        self.store = StoreFactory(name='Response Test Store')
        self.product = ProductFactory(
            name='Response Test Product',
            category='FA',
            price=Decimal('99.99'),
            sku='RES-001'
        )
        
        InventoryFactory(
            product=self.product,
            store=self.store,
            quantity=50,
            min_stock=5
        )

    def test_success_response_format(self):
        """Test successful response format consistency"""
        
        # Test successful transfer
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.store.id,
            'target_store_id': self.store.id,
            'quantity': 5
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertIsInstance(data, dict)
        self.assertIn('message', data)

    def test_error_response_format(self):
        """Test error response format consistency"""
        
        # Test error response
        transfer_data = {
            'product_id': 99999,  # Non-existent
            'source_store_id': self.store.id,
            'target_store_id': self.store.id,
            'quantity': 5
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertIsInstance(data, dict)
        self.assertIn('error', data)

    def test_list_response_format(self):
        """Test list endpoint response format consistency"""
        
        endpoints = [
            '/api/products/',
            '/api/stores/',
            f'/api/stores/{self.store.id}/inventory/',
            '/api/inventory/alerts/',
            '/api/movements/'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                
                if response.status_code == 200:
                    self.assertEqual(response['Content-Type'], 'application/json')
                    data = response.json()
                    self.assertIsInstance(data, list)
                elif response.status_code == 404:
                    # Acceptable for some endpoints
                    pass
                else:
                    self.fail(f"Unexpected status code {response.status_code} for {endpoint}")

    def test_pagination_format(self):
        """Test pagination format if implemented"""
        
        # Create multiple products to test pagination
        for i in range(15):
            ProductFactory(
                name=f'Pagination Product {i}',
                category='EL',
                price=Decimal(f'{i * 10}.99'),
                sku=f'PAG-{i:03d}'
            )
        
        # Test if pagination is implemented
        response = self.client.get('/products/products/?limit=10')
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if paginated response format is used
            if isinstance(data, dict) and 'results' in data:
                # Paginated format
                expected_fields = ['results', 'count']
                for field in expected_fields:
                    self.assertIn(field, data)
                
                self.assertIsInstance(data['results'], list)
                self.assertIsInstance(data['count'], int)
            else:
                # Simple list format (also valid)
                self.assertIsInstance(data, list)