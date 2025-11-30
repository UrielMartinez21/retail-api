# Django imports
from django.db.models import Sum
from django.http import HttpRequest, JsonResponse
from django.core.paginator import Paginator, EmptyPage

# Local imports
from .models import Product, Inventory, Store
from .helpers import (
    get_query_params, build_filters, build_response
)

# Standard library imports
import json
import logging

# Logger for this module
logger = logging.getLogger(__name__)

def handle_get_products(request: HttpRequest) -> JsonResponse:
    """
    Handle GET requests for the products endpoint.

    This function processes GET requests to retrieve a list of products based on
    filtering and pagination parameters. It applies filters, paginates the results,
    and returns a structured response containing product details and pagination metadata.

    Args:
        request (HttpRequest): The HTTP request object containing query parameters.

    Returns:
        JsonResponse: A JSON response containing the filtered and paginated list of products,
        along with pagination metadata. Returns an error response if the page number is out of range.
    """
    params = get_query_params(request)
    filters = build_filters(params)

    # Filter and paginate products
    filtered_products = Product.objects.filter(filters).prefetch_related("inventory_items").distinct()
    paginator = Paginator(filtered_products, int(params.get("page_size", 10)))

    try:
        products_page = paginator.page(int(params.get("page", 1)))
    except EmptyPage:
        return build_response("error", 400, "Page number out of range.")

    # Build product list
    products_list = [
        {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "category": product.get_category_display(),
            "price": str(product.price),
            "sku": product.sku,
            "total_stock": sum(item.quantity for item in product.inventory_items.all()),
        }
        for product in products_page
    ]

    return build_response(
        "success",
        200,
        data={
            "products": products_list,
            "pagination": {
                "current_page": products_page.number,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "page_size": paginator.per_page,
            },
        },
    )


def handle_post_product(request: HttpRequest) -> JsonResponse:
    """
    Handle POST requests for the products endpoint.

    This function processes POST requests to create a new product and its associated
    inventory in the database. It validates the request payload, ensures the store exists,
    and creates the product and inventory records.

    Args:
        request (HttpRequest): The HTTP request object containing the JSON payload.

    Returns:
        JsonResponse: A JSON response containing the details of the created product and inventory.
        Returns an error response if the payload is invalid, required fields are missing, or the store does not exist.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return build_response("error", 500, "Invalid JSON payload.")

    # Validate required fields
    required_fields = ["name", "description", "category", "price", "sku", "store_id", "quantity", "min_stock"]
    missing_fields = [field for field in required_fields if field not in body]
    if missing_fields:
        return build_response("error", 400, f"Missing required fields: {', '.join(missing_fields)}")

    # Validate store existence
    try:
        store = Store.objects.get(id=body["store_id"])
    except Store.DoesNotExist:
        return build_response("error", 400, "Store not found.")

    # Create product and inventory
    product = Product.objects.create(
        name=body["name"],
        description=body["description"],
        category=body["category"],
        price=body["price"],
        sku=body["sku"],
    )
    inventory = Inventory.objects.create(
        product=product,
        store=store,
        quantity=body["quantity"],
        min_stock=body["min_stock"],
    )

    return build_response(
        "success",
        200,
        data={
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "category": product.get_category_display(),
            "price": str(product.price),
            "sku": product.sku,
            "inventory": {
                "store_id": store.id,
                "store_name": store.name,
                "quantity": inventory.quantity,
                "min_stock": inventory.min_stock,
            },
        },
    )

def handle_get_product(product_id: int) -> JsonResponse:
    """
    Handle GET request for a specific product.

    This function retrieves the details of a specific product, including its total stock
    across all inventory items. If the product does not exist, an error response is returned.

    Args:
        product_id (int): The ID of the product to retrieve.

    Returns:
        JsonResponse: A JSON response containing the product details, including total stock.
        Returns an error response if the product does not exist.
    """
    try:
        product = Product.objects.prefetch_related("inventory_items").get(id=product_id)
        total_stock = product.inventory_items.aggregate(total=Sum("quantity"))["total"] or 0

        product_data = {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "category": product.get_category_display(),
            "price": str(product.price),
            "sku": product.sku,
            "total_stock": total_stock,
        }

        return build_response("success", 200, data=product_data)
    except Product.DoesNotExist:
        return build_response("error", 400, "Product not found.")


def handle_put_product(request: HttpRequest, product_id: int) -> JsonResponse:
    """
    Handle PUT request to update product details.

    This function processes PUT requests to update the details of an existing product.
    It updates the product fields, and if a store ID is provided, it updates or creates
    the associated inventory record. The function ensures that the product and store exist
    and validates the request payload.

    Args:
        request (HttpRequest): The HTTP request object containing the JSON payload.
        product_id (int): The ID of the product to update.

    Returns:
        JsonResponse: A JSON response containing the updated product details, including inventory
        information if applicable. Returns an error response if the product or store does not exist
        or if the payload is invalid.
    """
    try:
        body = json.loads(request.body)
        product = Product.objects.prefetch_related("inventory_items").get(id=product_id)

        # Update product fields if provided
        product.name = body.get("name", product.name)
        product.description = body.get("description", product.description)
        product.category = body.get("category", product.category)
        product.price = body.get("price", product.price)
        product.sku = body.get("sku", product.sku)
        product.save()

        # Update or create inventory if store_id is provided
        inventory_data = None
        if "store_id" in body:
            try:
                store = Store.objects.get(id=body["store_id"])
            except Store.DoesNotExist:
                return build_response("error", 400, "Store not found.")

            inventory, created = Inventory.objects.get_or_create(
                product=product,
                store=store,
                defaults={
                    "quantity": body.get("quantity", 0),
                    "min_stock": body.get("min_stock", 0),
                },
            )

            if not created:
                if "quantity" in body:
                    inventory.quantity = body["quantity"]
                if "min_stock" in body:
                    inventory.min_stock = body["min_stock"]
                inventory.save()

            inventory_data = {
                "store_id": store.id,
                "store_name": store.name,
                "quantity": inventory.quantity,
                "min_stock": inventory.min_stock,
                "created": created,
            }

        total_stock = product.inventory_items.aggregate(total=Sum("quantity"))[
            "total"
        ] or 0
        response_data = {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "category": product.get_category_display(),
            "price": str(product.price),
            "sku": product.sku,
            "total_stock": total_stock,
        }

        if inventory_data:
            response_data["inventory"] = inventory_data

        return build_response("success", 200, data=response_data)
    except Product.DoesNotExist:
        return build_response("error", 400, "Product not found.")
    except json.JSONDecodeError:
        return build_response("error", 400, "Invalid JSON payload.")


def handle_delete_product(product_id: int) -> JsonResponse:
    """
    Handle DELETE request to remove a product.

    This function processes DELETE requests to remove a product from the database.
    If the product exists, it is deleted. If the product does not exist, an error response is returned.

    Args:
        product_id (int): The ID of the product to delete.

    Returns:
        JsonResponse: A JSON response indicating the success or failure of the deletion operation.
    """
    try:
        product = Product.objects.get(id=product_id)
        product.delete()
        return build_response("success", 200, "Product deleted successfully.")
    except Product.DoesNotExist:
        return build_response("error", 400, "Product not found.")