# Testing Documentation

## Overview

Este proyecto incluye una suite completa de tests unitarios e integración para asegurar el correcto funcionamiento de la API de gestión de inventario retail. Los tests están diseñados para alcanzar un mínimo de 80% de cobertura de código.

## Estructura de Tests

```
products/tests/
├── __init__.py
├── factories.py          # Factory Boy factories para datos de prueba
├── test_models.py        # Tests para modelos Django
├── test_views.py         # Tests para vistas y endpoints
├── test_helpers.py       # Tests para funciones helper
├── test_handles.py       # Tests para manejadores de requests
└── test_integration.py   # Tests de integración completos
```

## Dependencias de Testing

Las siguientes librerías están incluidas en `requirements.txt`:

- **coverage==7.3.2**: Para medir cobertura de código
- **factory-boy==3.3.1**: Para generar datos de prueba de manera eficiente
- **faker==20.1.0**: Para generar datos realistas de prueba

## Ejecutar Tests

### Opción 1: Script de PowerShell (Recomendado)

```powershell
# Ejecutar todos los tests con coverage
.\run_tests.ps1

# Ejecutar tests sin coverage (modo rápido)
.\run_tests.ps1 -Quick

# Ejecutar un test específico
.\run_tests.ps1 -TestPath "products.tests.test_models.ProductModelTest.test_product_creation"
```

### Opción 2: Script de Python

```bash
# Ejecutar todos los tests con coverage
python run_tests.py

# Ejecutar un test específico
python run_tests.py products.tests.test_models
```

### Opción 3: Comandos Django directos

```powershell
# Ejecutar todos los tests
python manage.py test products.tests --verbosity=2

# Ejecutar con coverage
coverage run --rcfile=.coveragerc manage.py test products.tests
coverage report
coverage html
```

## Tipos de Tests

### 1. Tests de Modelos (`test_models.py`)

Cubren la funcionalidad de los modelos Django:

- **StoreModelTest**: Creación, validación y relaciones de tiendas
- **ProductModelTest**: Productos, categorías, validaciones y restricciones
- **InventoryModelTest**: Inventario, relaciones y restricciones únicas
- **MovementModelTest**: Movimientos de inventario y tipos

```python
class ProductModelTest(TestCase):
    def test_product_creation(self):
        """Test creating a product"""
        product = Product.objects.create(**self.product_data)
        self.assertEqual(product.name, 'Test Product')
        self.assertEqual(product.price, Decimal('99.99'))
```

### 2. Tests de Vistas (`test_views.py`)

Prueban los endpoints de la API:

- **ProductViewsTest**: GET/POST /products/
- **ProductDetailViewsTest**: GET/PUT/DELETE /products/{id}/
- **StoreViewsTest**: Gestión de tiendas
- **InventoryViewsTest**: Consultas de inventario
- **TransferViewsTest**: Transferencias entre tiendas

```python
def test_get_products_success(self):
    """Test GET /products/ returns all products"""
    response = self.client.get('/products/')
    self.assertEqual(response.status_code, 200)
    
    data = json.loads(response.content)
    self.assertEqual(data['status'], 'success')
```

### 3. Tests de Helpers (`test_helpers.py`)

Verifican funciones auxiliares:

- **GetQueryParamsTest**: Extracción de parámetros de query
- **BuildResponseTest**: Construcción de respuestas JSON
- **FetchProductAndStoresTest**: Obtención de entidades
- **ValidateRequestBodyTest**: Validación de datos de entrada
- **PerformInventoryTransferTest**: Lógica de transferencias

### 4. Tests de Handles (`test_handles.py`)

Prueban los manejadores de requests:

- **HandleGetProductsTest**: Manejo de listado de productos
- **HandlePostProductTest**: Creación de productos
- **HandleGetProductTest**: Obtención de producto individual
- **HandlePutProductTest**: Actualización de productos
- **HandleDeleteProductTest**: Eliminación de productos

### 5. Tests de Integración (`test_integration.py`)

Prueban flujos completos del sistema:

- **ProductManagementIntegrationTest**: Ciclo completo CRUD
- **DatabaseTransactionTest**: Atomicidad de transacciones

```python
def test_complete_product_lifecycle(self):
    """Test complete product lifecycle: create, read, update, delete"""
    # 1. Create
    response = self.client.post('/products/', data=json.dumps(new_product_data))
    
    # 2. Read
    response = self.client.get(f'/products/{product.id}/')
    
    # 3. Update
    response = self.client.put(f'/products/{product.id}/', data=json.dumps(update_data))
    
    # 4. Delete
    response = self.client.delete(f'/products/{product.id}/')
```

## Factories para Datos de Prueba

Los factories utilizan Factory Boy y Faker para generar datos realistas:

```python
class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product
    
    name = factory.LazyFunction(lambda: fake.catch_phrase())
    description = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    category = fuzzy.FuzzyChoice([choice[0] for choice in Product.Category.choices])
    price = factory.LazyFunction(lambda: Decimal(str(fake.pydecimal())))
    sku = factory.LazyFunction(lambda: fake.unique.lexify(text='???-###'))
```

## Configuración de Coverage

El archivo `.coveragerc` configura:

- **source**: Directorio fuente para medir cobertura
- **omit**: Archivos a excluir (migrations, tests, etc.)
- **exclude_lines**: Líneas a ignorar en coverage
- **html**: Directorio para reporte HTML

```ini
[run]
source = .
omit = 
    */migrations/*
    */tests/*
    manage.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
```

## Objetivos de Cobertura

- **Mínimo**: 80% de cobertura de código
- **Meta**: >90% de cobertura
- **Excluidos**: Archivos de configuración, migrations, tests

## Interpretación de Resultados

### Reporte de Console

```
Name                           Stmts   Miss  Cover
--------------------------------------------------
products/__init__.py               0      0   100%
products/models.py                45      2    96%
products/views.py                 85      8    91%
products/helpers.py               52      4    92%
products/handles.py               68      6    91%
--------------------------------------------------
TOTAL                            250     20    92%
```

### Reporte HTML

- Se genera en `htmlcov/index.html`
- Muestra líneas cubiertas y no cubiertas
- Navegación interactiva por archivos
- Resaltado de código con coverage

## Mocking y Patching

Los tests utilizan `unittest.mock` para:

- Mocking de loggers
- Simulación de errores de base de datos
- Aislamiento de funcionalidades externas

```python
@patch('products.views.logger')
def test_logging_in_views(self, mock_logger):
    """Test that views are logging properly"""
    response = self.client.get('/products/')
    mock_logger.info.assert_called()
```

## Casos de Prueba Importantes

### 1. Validaciones de Negocio

- SKU único en productos
- Cantidad suficiente en transferencias
- Restricciones de integridad de datos

### 2. Manejo de Errores

- Productos inexistentes
- Datos de entrada inválidos
- Errores de base de datos

### 3. Casos Límite

- Transferencias con cantidad exacta disponible
- Creación de inventario en tiendas nuevas
- Actualizaciones parciales de productos

## Mejores Prácticas

### 1. Estructura de Tests

```python
class ModelTest(TestCase):
    def setUp(self):
        """Set up test data"""
        self.model_data = {...}
    
    def test_specific_functionality(self):
        """Test specific functionality with descriptive name"""
        # Arrange
        # Act  
        # Assert
```

### 2. Nombres Descriptivos

- `test_product_creation_success`
- `test_transfer_insufficient_stock`
- `test_handle_get_products_with_filters`

### 3. Assertions Específicas

```python
# Malo
self.assertTrue(response.status_code == 200)

# Bueno
self.assertEqual(response.status_code, 200)
```

### 4. Datos de Prueba

- Usar factories en lugar de datos hardcoded
- Crear datos mínimos necesarios para cada test
- Limpiar datos entre tests (automático con TestCase)

## CI/CD Integration

Para integración continua, agregar al pipeline:

```yaml
- name: Run Tests with Coverage
  run: |
    python run_tests.py
    coverage xml
    
- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Debugging Tests

### Ejecutar con Debug

```powershell
# Con más verbosidad
python manage.py test products.tests --verbosity=3

# Un test específico
python manage.py test products.tests.test_models.ProductModelTest.test_product_creation -v 2
```

### Logs en Tests

Los tests incluyen logging, que se puede habilitar:

```python
import logging
logging.disable(logging.NOTSET)  # En setUp para ver logs durante tests
```

## Mantenimiento de Tests

1. **Actualizar factories** cuando cambien modelos
2. **Revisar coverage** después de agregar funcionalidad
3. **Refactorizar tests** cuando sea necesario
4. **Documentar casos especiales** en docstrings

## Troubleshooting

### Problemas Comunes

1. **Tests fallan localmente**: Verificar base de datos de test
2. **Coverage bajo**: Revisar archivos excluidos en .coveragerc
3. **Factory errors**: Verificar datos únicos (sku, etc.)
4. **Import errors**: Verificar PYTHONPATH y DJANGO_SETTINGS_MODULE

### Comandos Útiles

```powershell
# Limpiar cache de coverage
coverage erase

# Ver tests disponibles
python manage.py test --help

# Ejecutar con pdb para debugging
python manage.py test products.tests.test_models --pdb
```