# Test runner script for PowerShell
# Runs Django tests with coverage reporting

param(
    [string]$TestPath = "",
    [switch]$Quick = $false
)

Write-Host "🧪 Django Test Runner with Coverage" -ForegroundColor Cyan

# Set Django settings
$env:DJANGO_SETTINGS_MODULE = "retail_api.settings"

try {
    if ($TestPath) {
        # Run specific test
        Write-Host "Running specific test: $TestPath" -ForegroundColor Yellow
        python manage.py test $TestPath --verbosity=2
    } elseif ($Quick) {
        # Run tests without coverage (faster)
        Write-Host "Running tests without coverage (quick mode)" -ForegroundColor Yellow
        python manage.py test products.tests --verbosity=2
    } else {
        # Run full test suite with coverage
        Write-Host "Running full test suite with coverage..." -ForegroundColor Yellow
        
        # Check if coverage is installed
        $coverageCheck = python -c "import coverage" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Coverage not installed. Installing..." -ForegroundColor Red
            pip install coverage
        }
        
        # Run tests with coverage
        coverage run --rcfile=.coveragerc manage.py test products.tests --verbosity=2
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Tests completed successfully!" -ForegroundColor Green
            
            # Generate reports
            Write-Host "`n📊 Generating coverage reports..." -ForegroundColor Cyan
            
            # Console report
            coverage report
            
            # HTML report
            coverage html
            Write-Host "📄 HTML coverage report generated in htmlcov/index.html" -ForegroundColor Green
            
            # Check coverage percentage
            $coverageOutput = coverage report --format=total 2>$null
            if ($LASTEXITCODE -eq 0) {
                $coveragePercentage = [double]$coverageOutput
                Write-Host "`n📈 Total coverage: $($coveragePercentage)%" -ForegroundColor Cyan
                
                if ($coveragePercentage -ge 80) {
                    Write-Host "✅ Coverage target of 80% achieved!" -ForegroundColor Green
                } else {
                    Write-Host "⚠️  Coverage below 80% target" -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "❌ Tests failed!" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "❌ Error running tests: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n🎉 Test run completed!" -ForegroundColor Green