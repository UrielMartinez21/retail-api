#!/usr/bin/env python3
"""
Script to fix URL prefixes in integration tests
Replace /products/ with /api/ in test files
"""

import os
import re

# Define file paths
test_files = [
    'c:/Users/uriel/OneDrive/Escritorio/Uriel/Python/django/retail_api/products/tests/test_integration.py',
    'c:/Users/uriel/OneDrive/Escritorio/Uriel/Python/django/retail_api/products/tests/test_performance.py',
    'c:/Users/uriel/OneDrive/Escritorio/Uriel/Python/django/retail_api/products/tests/test_api_integration.py'
]

# URL mappings to fix
url_mappings = [
    (r"'/products/products/'", "'/api/products/'"),
    (r"'/products/stores/'", "'/api/stores/'"),
    (r"'/products/inventory/transfer/'", "'/api/inventory/transfer/'"),
    (r"'/products/inventory/alerts/'", "'/api/inventory/alerts/'"),
    (r"'/products/movements/'", "'/api/movements/'"),
    (r"f'/products/products/{", "f'/api/products/{"),
    (r"f'/products/stores/{", "f'/api/stores/{"),
    (r"'/products/'", "'/api/products/'"),
    (r"'/stores/'", "'/api/stores/'"),
    (r"'/transfer/'", "'/api/inventory/transfer/'"),
    (r"'/products/\?", "'/api/products/?"),
    (r"f'/products/stores/\{", "f'/api/stores/{"),
]

def fix_urls_in_file(file_path):
    """Fix URLs in a single file"""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all URL mappings
        for old_pattern, new_pattern in url_mappings:
            content = re.sub(old_pattern, new_pattern, content)
        
        # Write back if changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated URLs in: {file_path}")
        else:
            print(f"No changes needed in: {file_path}")
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main():
    """Main function"""
    print("Fixing URL prefixes in test files...")
    
    for file_path in test_files:
        fix_urls_in_file(file_path)
    
    print("URL fixing complete!")

if __name__ == '__main__':
    main()