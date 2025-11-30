#!/usr/bin/env python
"""
Test runner script with coverage reporting
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_tests_with_coverage():
    """Run tests with coverage reporting"""
    print("🧪 Running tests with coverage...")
    
    # Set Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'retail_api.settings')
    
    try:
        # Run coverage with Django test command
        cmd = [
            'coverage', 'run', 
            '--rcfile=.coveragerc',
            'manage.py', 'test', 
            'products.tests',
            '--verbosity=2'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode != 0:
            print(f"❌ Tests failed with return code {result.returncode}")
            return False
        
        print("✅ Tests completed successfully!")
        
        # Generate coverage report
        print("\n📊 Generating coverage report...")
        
        # Console report
        subprocess.run(['coverage', 'report'], check=True)
        
        # HTML report
        subprocess.run(['coverage', 'html'], check=True)
        print("📄 HTML coverage report generated in htmlcov/index.html")
        
        # Check coverage percentage
        result = subprocess.run(['coverage', 'report', '--format=total'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            coverage_percentage = float(result.stdout.strip())
            print(f"\n📈 Total coverage: {coverage_percentage:.1f}%")
            
            if coverage_percentage >= 80:
                print("✅ Coverage target of 80% achieved!")
                return True
            else:
                print("⚠️  Coverage below 80% target")
                return False
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running tests: {e}")
        return False
    except FileNotFoundError:
        print("❌ Coverage not installed. Install with: pip install coverage")
        return False

def run_specific_test(test_path):
    """Run a specific test"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'retail_api.settings')
    
    cmd = ['python', 'manage.py', 'test', test_path, '--verbosity=2']
    result = subprocess.run(cmd)
    return result.returncode == 0

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test
        test_path = sys.argv[1]
        print(f"🧪 Running specific test: {test_path}")
        success = run_specific_test(test_path)
    else:
        # Run all tests with coverage
        success = run_tests_with_coverage()
    
    sys.exit(0 if success else 1)