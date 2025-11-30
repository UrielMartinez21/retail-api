"""
Performance and Stress Tests for Critical Business Flows

These tests focus on system behavior under stress conditions,
performance benchmarks, and edge case scenarios.
"""

import json
import threading
import time
from decimal import Decimal
from django.test import TestCase, TransactionTestCase, Client
from django.db import transaction, connection
from django.test.utils import override_settings
from unittest.mock import patch

from products.models import Store, Product, Inventory, Movement
from products.tests.factories import StoreFactory, ProductFactory, InventoryFactory


class PerformanceIntegrationTest(TestCase):
    """Performance-focused integration tests"""
    
    def setUp(self):
        """Set up performance test data"""
        self.client = Client()
        
        # Create a realistic store setup
        self.stores = [
            StoreFactory(name=f'Store {i}') for i in range(10)
        ]
        self.warehouse = StoreFactory(name='Central Warehouse')
        
        # Create various product types
        self.products = []
        categories = ['EL', 'FU', 'SP', 'FA']
        
        for i in range(50):  # 50 different products
            product = ProductFactory(
                name=f'Product {i}',
                category=categories[i % 4],
                price=Decimal(f'{10 + (i * 5)}.99'),
                sku=f'PROD-{i:03d}'
            )
            self.products.append(product)
            
            # Create warehouse inventory
            InventoryFactory(
                product=product,
                store=self.warehouse,
                quantity=1000,
                min_stock=100
            )
            
            # Create random inventory in stores
            for j, store in enumerate(self.stores[:5]):  # Only first 5 stores
                if (i + j) % 3 == 0:  # Not all products in all stores
                    InventoryFactory(
                        product=product,
                        store=store,
                        quantity=50 + (i * 2),
                        min_stock=10
                    )

    def test_bulk_transfer_performance(self):
        """Test performance of bulk transfer operations"""
        start_time = time.time()
        
        # Perform 100 transfer operations
        transfer_count = 100
        successful_transfers = 0
        
        for i in range(transfer_count):
            product = self.products[i % len(self.products)]
            source_store = self.warehouse
            target_store = self.stores[i % len(self.stores)]
            
            transfer_data = {
                'product_id': product.id,
                'source_store_id': source_store.id,
                'target_store_id': target_store.id,
                'quantity': 5
            }
            
            response = self.client.post(
                '/api/inventory/transfer/',
                data=json.dumps(transfer_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                successful_transfers += 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(total_time, 30.0, 
                       f"100 transfers should complete within 30 seconds, took {total_time:.2f}")
        self.assertGreaterEqual(successful_transfers, 95, 
                               f"At least 95% transfers should succeed, got {successful_transfers}")
        
        # Calculate throughput
        throughput = successful_transfers / total_time
        self.assertGreater(throughput, 3.0, 
                          f"Should handle at least 3 transfers/second, got {throughput:.2f}")

    def test_concurrent_read_operations(self):
        """Test system performance under concurrent read operations"""
        
        def read_operations():
            """Perform multiple read operations"""
            operations = [
                lambda: self.client.get('/api/products/'),
                lambda: self.client.get('/api/stores/'),
                lambda: self.client.get('/api/inventory/alerts/'),
                lambda: self.client.get('/api/movements/'),
            ]
            
            results = []
            for _ in range(25):  # 25 operations per thread
                operation = operations[_ % len(operations)]
                start = time.time()
                response = operation()
                end = time.time()
                results.append({
                    'status': response.status_code,
                    'duration': end - start
                })
            return results
        
        # Start 4 concurrent threads
        threads = []
        thread_results = {}
        
        def worker(thread_id):
            thread_results[thread_id] = read_operations()
        
        start_time = time.time()
        
        for i in range(4):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze results
        all_results = []
        for results in thread_results.values():
            all_results.extend(results)
        
        successful_ops = sum(1 for r in all_results if r['status'] == 200)
        avg_response_time = sum(r['duration'] for r in all_results) / len(all_results)
        
        # Performance assertions
        self.assertLess(total_time, 15.0, 
                       f"Concurrent reads should complete within 15 seconds, took {total_time:.2f}")
        self.assertGreaterEqual(successful_ops / len(all_results), 0.95,
                               "At least 95% of concurrent reads should succeed")
        self.assertLess(avg_response_time, 1.0,
                       f"Average response time should be under 1 second, got {avg_response_time:.3f}")

    def test_mixed_workload_performance(self):
        """Test system performance under mixed read/write workload"""
        
        def mixed_workload():
            """Perform mixed operations"""
            results = []
            
            for i in range(20):
                if i % 4 == 0:
                    # Write operation: transfer
                    product = self.products[i % len(self.products)]
                    transfer_data = {
                        'product_id': product.id,
                        'source_store_id': self.warehouse.id,
                        'target_store_id': self.stores[i % len(self.stores)].id,
                        'quantity': 2
                    }
                    
                    start = time.time()
                    response = self.client.post(
                        '/api/inventory/transfer/',
                        data=json.dumps(transfer_data),
                        content_type='application/json'
                    )
                    end = time.time()
                else:
                    # Read operations
                    endpoints = [
                        '/api/products/',
                        '/api/stores/',
                        f'/api/stores/{self.warehouse.id}/inventory/'
                    ]
                    endpoint = endpoints[i % len(endpoints)]
                    
                    start = time.time()
                    response = self.client.get(endpoint)
                    end = time.time()
                
                results.append({
                    'status': response.status_code,
                    'duration': end - start,
                    'type': 'write' if i % 4 == 0 else 'read'
                })
            
            return results
        
        # Run mixed workload
        start_time = time.time()
        results = mixed_workload()
        end_time = time.time()
        
        total_time = end_time - start_time
        
        # Analyze results
        read_ops = [r for r in results if r['type'] == 'read']
        write_ops = [r for r in results if r['type'] == 'write']
        
        successful_reads = sum(1 for r in read_ops if r['status'] == 200)
        successful_writes = sum(1 for r in write_ops if r['status'] == 200)
        
        avg_read_time = sum(r['duration'] for r in read_ops) / len(read_ops)
        avg_write_time = sum(r['duration'] for r in write_ops) / len(write_ops)
        
        # Performance assertions
        self.assertLess(total_time, 10.0, "Mixed workload should complete within 10 seconds")
        self.assertGreaterEqual(successful_reads / len(read_ops), 0.95, 
                               "95% of reads should succeed")
        self.assertGreaterEqual(successful_writes / len(write_ops), 0.9, 
                               "90% of writes should succeed")
        self.assertLess(avg_read_time, 0.5, "Average read time should be under 0.5 seconds")
        self.assertLess(avg_write_time, 2.0, "Average write time should be under 2 seconds")


class StressTestIntegrationTest(TransactionTestCase):
    """Stress testing for edge cases and system limits"""
    
    def setUp(self):
        """Set up stress test data"""
        self.client = Client()
        
        # Minimal setup for stress testing
        self.warehouse = StoreFactory(name='Stress Test Warehouse')
        self.retail_store = StoreFactory(name='Stress Test Retail')
        
        self.test_product = ProductFactory(
            name='Stress Test Product',
            category='EL',
            price=Decimal('99.99'),
            sku='STRESS-001'
        )
        
        self.warehouse_inventory = InventoryFactory(
            product=self.test_product,
            store=self.warehouse,
            quantity=10000,  # Large quantity for stress testing
            min_stock=1000
        )

    def test_rapid_concurrent_transfers(self):
        """Test system under rapid concurrent transfer requests"""
        
        def rapid_transfers(thread_id):
            """Perform rapid transfers"""
            results = []
            for i in range(10):
                transfer_data = {
                    'product_id': self.test_product.id,
                    'source_store_id': self.warehouse.id,
                    'target_store_id': self.retail_store.id,
                    'quantity': 1
                }
                
                try:
                    response = self.client.post(
                        '/api/inventory/transfer/',
                        data=json.dumps(transfer_data),
                        content_type='application/json'
                    )
                    results.append(response.status_code)
                except Exception as e:
                    results.append(f"Error: {str(e)}")
            
            return results
        
        # Start multiple threads for concurrent stress
        threads = []
        thread_results = {}
        
        def worker(thread_id):
            thread_results[thread_id] = rapid_transfers(thread_id)
        
        # Start 5 concurrent threads
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Analyze results
        all_results = []
        for results in thread_results.values():
            all_results.extend(results)
        
        successful_transfers = sum(1 for r in all_results if r == 200)
        
        # Stress test assertions
        self.assertGreater(successful_transfers, 30, 
                          "Should handle at least 30 concurrent transfers")
        
        # Verify final inventory state is consistent
        self.warehouse_inventory.refresh_from_db()
        retail_inventory = Inventory.objects.get(
            product=self.test_product,
            store=self.retail_store
        )
        
        total_transferred = successful_transfers
        expected_warehouse = 10000 - total_transferred
        
        self.assertEqual(self.warehouse_inventory.quantity, expected_warehouse)
        self.assertEqual(retail_inventory.quantity, total_transferred)

    def test_large_quantity_transfers(self):
        """Test handling of very large quantity transfers"""
        
        # Test transferring a very large quantity
        large_quantity = 5000
        
        transfer_data = {
            'product_id': self.test_product.id,
            'source_store_id': self.warehouse.id,
            'target_store_id': self.retail_store.id,
            'quantity': large_quantity
        }
        
        start_time = time.time()
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        end_time = time.time()
        
        # Should succeed
        self.assertEqual(response.status_code, 200)
        
        # Should complete in reasonable time
        transfer_time = end_time - start_time
        self.assertLess(transfer_time, 5.0, 
                       f"Large transfer should complete within 5 seconds, took {transfer_time:.2f}")
        
        # Verify correct quantities
        self.warehouse_inventory.refresh_from_db()
        retail_inventory = Inventory.objects.get(
            product=self.test_product,
            store=self.retail_store
        )
        
        self.assertEqual(self.warehouse_inventory.quantity, 5000)  # 10000 - 5000
        self.assertEqual(retail_inventory.quantity, 5000)

    def test_boundary_conditions(self):
        """Test edge cases and boundary conditions"""
        
        # Test 1: Transfer exact available quantity
        available_quantity = self.warehouse_inventory.quantity
        
        transfer_data = {
            'product_id': self.test_product.id,
            'source_store_id': self.warehouse.id,
            'target_store_id': self.retail_store.id,
            'quantity': available_quantity
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Warehouse should be empty
        self.warehouse_inventory.refresh_from_db()
        self.assertEqual(self.warehouse_inventory.quantity, 0)
        
        # Test 2: Try to transfer from empty warehouse
        transfer_data['quantity'] = 1
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)  # Should fail

    def test_system_recovery_after_errors(self):
        """Test system recovery and consistency after error conditions"""
        
        # Create error condition: Invalid data
        invalid_transfers = [
            {
                'product_id': 99999,  # Non-existent product
                'source_store_id': self.warehouse.id,
                'target_store_id': self.retail_store.id,
                'quantity': 10
            },
            {
                'product_id': self.test_product.id,
                'source_store_id': 99999,  # Non-existent store
                'target_store_id': self.retail_store.id,
                'quantity': 10
            },
            {
                'product_id': self.test_product.id,
                'source_store_id': self.warehouse.id,
                'target_store_id': self.retail_store.id,
                'quantity': -10  # Negative quantity
            }
        ]
        
        # Attempt invalid transfers
        for transfer_data in invalid_transfers:
            response = self.client.post(
                '/api/inventory/transfer/',
                data=json.dumps(transfer_data),
                content_type='application/json'
            )
            self.assertNotEqual(response.status_code, 200, 
                              "Invalid transfers should fail")
        
        # Verify system is still functional with valid transfer
        valid_transfer = {
            'product_id': self.test_product.id,
            'source_store_id': self.warehouse.id,
            'target_store_id': self.retail_store.id,
            'quantity': 10
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(valid_transfer),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200, 
                        "System should recover and handle valid transfers")


class SecurityIntegrationTest(TestCase):
    """Security-focused integration tests"""
    
    def setUp(self):
        """Set up security test data"""
        self.client = Client()
        
        self.store = StoreFactory(name='Security Test Store')
        self.product = ProductFactory(
            name='Security Test Product',
            category='EL',
            price=Decimal('50.00'),
            sku='SEC-001'
        )
        
        InventoryFactory(
            product=self.product,
            store=self.store,
            quantity=100,
            min_stock=10
        )

    def test_sql_injection_protection(self):
        """Test protection against SQL injection attacks"""
        
        # Test SQL injection in product search
        malicious_inputs = [
            "'; DROP TABLE products_product; --",
            "' OR 1=1 --",
            "'; UPDATE products_inventory SET quantity = 0; --"
        ]
        
        for malicious_input in malicious_inputs:
            response = self.client.get(
                f'/products/products/?category={malicious_input}'
            )
            # Should not cause errors and should return safe response
            self.assertIn(response.status_code, [200, 400])
        
        # Verify data integrity after attempts
        self.assertEqual(Product.objects.count(), 1)  # Should still have our test product
        inventory = Inventory.objects.get(product=self.product)
        self.assertEqual(inventory.quantity, 100)  # Quantity should be unchanged

    def test_data_validation_and_sanitization(self):
        """Test input validation and sanitization"""
        
        # Test invalid data types
        invalid_transfers = [
            {
                'product_id': 'invalid',
                'source_store_id': self.store.id,
                'target_store_id': self.store.id,
                'quantity': 10
            },
            {
                'product_id': self.product.id,
                'source_store_id': self.store.id,
                'target_store_id': self.store.id,
                'quantity': 'invalid'
            },
            {
                'product_id': None,
                'source_store_id': self.store.id,
                'target_store_id': self.store.id,
                'quantity': 10
            }
        ]
        
        for invalid_data in invalid_transfers:
            response = self.client.post(
                '/api/inventory/transfer/',
                data=json.dumps(invalid_data),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 400, 
                           "Invalid data should be rejected")

    def test_rate_limiting_simulation(self):
        """Test behavior under rapid request patterns"""
        
        # Simulate rapid requests from same client
        rapid_requests = []
        
        for i in range(50):
            response = self.client.get('/api/products/')
            rapid_requests.append(response.status_code)
            
            # Small delay to avoid overwhelming the test
            time.sleep(0.01)
        
        # System should remain responsive
        successful_requests = sum(1 for status in rapid_requests if status == 200)
        self.assertGreater(successful_requests / len(rapid_requests), 0.8,
                          "System should handle most rapid requests successfully")


class DataIntegrityIntegrationTest(TestCase):
    """Tests focused on data integrity and consistency"""
    
    def setUp(self):
        """Set up data integrity test environment"""
        self.client = Client()
        
        self.store_a = StoreFactory(name='Integrity Store A')
        self.store_b = StoreFactory(name='Integrity Store B')
        
        self.product = ProductFactory(
            name='Integrity Test Product',
            category='EL',
            price=Decimal('75.00'),
            sku='INT-001'
        )
        
        self.inventory_a = InventoryFactory(
            product=self.product,
            store=self.store_a,
            quantity=200,
            min_stock=20
        )
        
        self.inventory_b = InventoryFactory(
            product=self.product,
            store=self.store_b,
            quantity=50,
            min_stock=10
        )

    def test_inventory_balance_consistency(self):
        """Test that inventory balances remain consistent across operations"""
        
        # Record initial total
        initial_total = self.inventory_a.quantity + self.inventory_b.quantity
        
        # Perform multiple transfers
        transfers = [
            {'quantity': 25, 'source': self.store_a, 'target': self.store_b},
            {'quantity': 15, 'source': self.store_b, 'target': self.store_a},
            {'quantity': 30, 'source': self.store_a, 'target': self.store_b},
        ]
        
        for transfer in transfers:
            transfer_data = {
                'product_id': self.product.id,
                'source_store_id': transfer['source'].id,
                'target_store_id': transfer['target'].id,
                'quantity': transfer['quantity']
            }
            
            response = self.client.post(
                '/api/inventory/transfer/',
                data=json.dumps(transfer_data),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
        
        # Verify total inventory remains the same
        self.inventory_a.refresh_from_db()
        self.inventory_b.refresh_from_db()
        
        final_total = self.inventory_a.quantity + self.inventory_b.quantity
        self.assertEqual(initial_total, final_total,
                        "Total inventory should remain constant")

    def test_movement_record_accuracy(self):
        """Test that movement records accurately reflect actual transfers"""
        
        initial_movements = Movement.objects.count()
        
        # Perform transfers
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.store_a.id,
            'target_store_id': self.store_b.id,
            'quantity': 40
        }
        
        response = self.client.post(
            '/api/inventory/transfer/',
            data=json.dumps(transfer_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify movement record
        final_movements = Movement.objects.count()
        self.assertEqual(final_movements, initial_movements + 1)
        
        movement = Movement.objects.latest('timestamp')
        self.assertEqual(movement.product, self.product)
        self.assertEqual(movement.source_store, self.store_a)
        self.assertEqual(movement.target_store, self.store_b)
        self.assertEqual(movement.quantity, 40)
        self.assertEqual(movement.type, 'TRANSFER')

    def test_concurrent_modification_handling(self):
        """Test handling of concurrent modifications to same inventory"""
        
        # This test simulates race conditions
        # In a real scenario, this would be more complex with actual threading
        
        original_quantity = self.inventory_a.quantity
        
        # Simulate concurrent updates by performing rapid transfers
        transfer_data = {
            'product_id': self.product.id,
            'source_store_id': self.store_a.id,
            'target_store_id': self.store_b.id,
            'quantity': 5
        }
        
        successful_transfers = 0
        for i in range(10):
            response = self.client.post(
                '/api/inventory/transfer/',
                data=json.dumps(transfer_data),
                content_type='application/json'
            )
            if response.status_code == 200:
                successful_transfers += 1
        
        # Verify final state is consistent
        self.inventory_a.refresh_from_db()
        self.inventory_b.refresh_from_db()
        
        expected_a_quantity = original_quantity - (successful_transfers * 5)
        self.assertEqual(self.inventory_a.quantity, expected_a_quantity)