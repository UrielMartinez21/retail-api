# Django imports
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

# Local imports
from .models import Product
from .helpers import get_query_params, build_filters, build_pagination_params

# Standard library imports
import json


@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def products(request: HttpRequest) -> HttpResponse:
    response = {"status": "error", "message": "", "data": None}
    try:
        if request.method == "OPTIONS":
            response["status"] = "success"

        elif request.method == "GET":
            # Extract query parameters
            params = get_query_params(request)

            # Build filters and apply them
            filters = build_filters(params)
            filtered_products = Product.objects.filter(filters).prefetch_related('inventory_items').distinct()

            # Build pagination
            paginator, products_page = build_pagination_params(
                filtered_products, int(params["page"]), int(params["page_size"])
            )

            # Build the products list
            products_list = []
            for product in products_page:
                total_stock = sum(item.quantity for item in product.inventory_items.all())
                products_list.append({
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "category": product.get_category_display(),
                    "price": str(product.price),
                    "sku": product.sku,
                    "total_stock": total_stock,
                })

            # Build response
            response["status"] = "success"
            response["data"] = {
                "products": products_list,
                "pagination": {
                    "current_page": int(params["page"]),
                    "total_pages": paginator.num_pages,
                    "total_items": paginator.count,
                    "page_size": int(params["page_size"]),
                },
            }

        elif request.method == "POST":
            body = json.loads(request.body)

            # Validate the required data
            required_fields = [
                "name",
                "description",
                "category",
                "price",
                "sku",
            ]
            for field in required_fields:
                if field not in body:
                    response["message"] = f"El campo '{field}' es obligatorio."
                    return JsonResponse(response, status=400)

            # Create the product
            product = Product.objects.create(
                name=body["name"],
                description=body["description"],
                category=body["category"],
                price=body["price"],
                sku=body["sku"],
            )

            response["status"] = "success"
            response["data"] = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.get_category_display(),
                "price": str(product.price),
            }

        return JsonResponse(response, status=200)
    except Exception as e:
        response["message"] = str(e)
        return JsonResponse(response, status=500)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE", "OPTIONS"])
def product_detail(request: HttpRequest, product_id: int) -> HttpResponse:
    """Handle individual product operations (CRUD operations).

    This view provides comprehensive single product management functionality:
    - GET: Retrieve specific product details by ID
    - PUT: Update existing product with partial or complete data
    - DELETE: Remove product from database
    - OPTIONS: CORS preflight support

    URL Parameters:
        product_id (int): The unique identifier of the product to operate on

    Request Body (PUT requests only):
        JSON object containing any of the following optional fields:
        - name (str): Product name (max 100 characters)
        - description (str): Product description
        - category (str): Product category code ('EL', 'FA', 'HO', 'TO', 'SP')
        - price (float): Product price (must be positive)
        - stock (int): Stock quantity (must be non-negative)
        Note: SKU cannot be updated for data integrity

    Args:
        request: The HTTP request object containing method, headers, and body
        product_id: The unique identifier of the product to retrieve/modify/delete

    Returns:
        JsonResponse: JSON response with following structure:
            - status (str): 'success' or 'error'
            - message (str): Success/error message or empty string
            - data (dict or None): Response payload containing:
                For GET/PUT: {
                    'id': int,
                    'name': str,
                    'description': str,
                    'category': str (display name),
                    'price': str (decimal formatted),
                    'stock': int,
                    'sku': str
                }
                For DELETE: None (data is null)

    Response Codes:
        200: Successful operation
        400: Bad request (invalid JSON, validation errors)
        404: Product not found
        500: Internal server error

    Raises:
        Product.DoesNotExist: When product with given ID doesn't exist
        JSONDecodeError: When PUT request contains invalid JSON
        ValidationError: When product data validation fails
        DatabaseError: When database operations fail

    Example:
        GET /api/products/123/
        PUT /api/products/123/
        {
            "name": "Updated Smartphone",
            "price": 649.99,
            "stock": 15
        }
        DELETE /api/products/123/
    """
    response = {"status": "error", "message": "", "data": None}
    try:
        if request.method == "OPTIONS":
            response["status"] = "success"

        elif request.method == "GET":
            product = Product.objects.prefetch_related('inventory_items').get(id=product_id)
            total_stock = sum(item.quantity for item in product.inventory_items.all())
            product_data = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.get_category_display(),
                "price": str(product.price),
                "sku": product.sku,
                "total_stock": total_stock,
            }
            response["status"] = "success"
            response["data"] = product_data

        elif request.method == "PUT":
            body = json.loads(request.body)
            product = Product.objects.prefetch_related('inventory_items').get(id=product_id)

            # Update product fields if provided
            product.name = body.get("name", product.name)
            product.description = body.get("description", product.description)
            product.category = body.get("category", product.category)
            product.price = body.get("price", product.price)
            product.save()

            total_stock = sum(item.quantity for item in product.inventory_items.all())
            response["status"] = "success"
            response["data"] = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.get_category_display(),
                "price": str(product.price),
                "total_stock": total_stock,
            }

        elif request.method == "DELETE":
            product = Product.objects.get(id=product_id)
            product.delete()
            response["status"] = "success"
            response["message"] = "Product deleted successfully."

        return JsonResponse(response, status=200)
    except Product.DoesNotExist:
        response["message"] = "Product not found."
        return JsonResponse(response, status=404)
    except Exception as e:
        response["message"] = str(e)
        return JsonResponse(response, status=500)
