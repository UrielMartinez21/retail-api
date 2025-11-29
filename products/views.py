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
def all_products(request: HttpRequest) -> HttpResponse:
    """
    View to return filtered products in JSON format with pagination.
    Filters can be applied using query parameters:
        - category: Filter by category (e.g., 'EL', 'FA', etc.)
        - min_price: Minimum price (e.g., 10.00)
        - max_price: Maximum price (e.g., 100.00)
        - in_stock: Filter products with stock > 0 (e.g., 'true' or 'false')
    Pagination parameters:
        - page: Page number (e.g., 1, 2, 3, etc.)
        - page_size: Number of items per page (default: 10)
    Args:
        request (HttpRequest): The HTTP request object.
    Returns:
        JsonResponse: A JSON response containing paginated and filtered products.
    """
    response = {"status": "error", "message": "", "data": None}
    try:
        if request.method == "OPTIONS":
            response["status"] = "success"

        elif request.method == "GET":
            # Extract query parameters
            params = get_query_params(request)

            # Build filters and apply them
            filters = build_filters(params)
            filtered_products = Product.objects.filter(filters)

            # Build pagination
            paginator, products_page = build_pagination_params(
                filtered_products, int(params["page"]), int(params["page_size"])
            )

            # Build the products list
            products_list = [
                {
                    "name": product.name,
                    "description": product.description,
                    "category": product.get_category_display(),
                    "price": str(product.price),
                    "stock": product.stock_quantity,
                }
                for product in products_page
            ]

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
            required_fields = ["name", "description", "category", "price", "stock"]
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
                stock_quantity=body["stock"],
            )

            response["status"] = "success"
            response["data"] = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.get_category_display(),
                "price": str(product.price),
                "stock": product.stock_quantity,
            }

        return JsonResponse(response, status=200)
    except Exception as e:
        response["message"] = str(e)
        return JsonResponse(response, status=500)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE", "OPTIONS"])
def product_detail(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    View to return the details of a specific product by its ID in JSON format.
    Args:
        request (HttpRequest): The HTTP request object.
        product_id (int): The ID of the product to retrieve.
    Returns:
        JsonResponse: A JSON response containing the product details.
    """
    response = {"status": "error", "message": "", "data": None}
    try:
        if request.method == "OPTIONS":
            response["status"] = "success"
            return JsonResponse(response, status=200)

        elif request.method == "GET":
            product = Product.objects.get(id=product_id)
            product_data = {
                "name": product.name,
                "description": product.description,
                "category": product.get_category_display(),
                "price": str(product.price),
                "stock": product.stock_quantity,
            }
            response["status"] = "success"
            response["data"] = product_data
            return JsonResponse(response, status=200)
        elif request.method == "PUT":
            body = json.loads(request.body)
            product = Product.objects.get(id=product_id)

            # Update product fields if provided
            product.name = body.get("name", product.name)
            product.description = body.get("description", product.description)
            product.category = body.get("category", product.category)
            product.price = body.get("price", product.price)
            product.stock_quantity = body.get("stock", product.stock_quantity)
            product.save()

            response["status"] = "success"
            response["data"] = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.get_category_display(),
                "price": str(product.price),
                "stock": product.stock_quantity,
            }
            return JsonResponse(response, status=200)
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
