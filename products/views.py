# Django imports
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

# Local imports
from .models import Product, Store, Inventory
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
                "store_id",
                "quantity",
                "min_stock",
            ]
            for field in required_fields:
                if field not in body:
                    response["message"] = f"El campo '{field}' es obligatorio."
                    return JsonResponse(response, status=400)

            # Get the store
            try:
                store = Store.objects.get(id=body["store_id"])
            except Store.DoesNotExist:
                response["message"] = "Store not found."
                return JsonResponse(response, status=400)

            # Create the product
            product = Product.objects.create(
                name=body["name"],
                description=body["description"],
                category=body["category"],
                price=body["price"],
                sku=body["sku"],
            )

            # Create inventory entry
            inventory = Inventory.objects.create(
                product=product,
                store=store,
                quantity=body["quantity"],
                min_stock=body["min_stock"],
            )

            response["status"] = "success"
            response["data"] = {
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
            }

        return JsonResponse(response, status=200)
    except Exception as e:
        response["message"] = str(e)
        return JsonResponse(response, status=500)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE", "OPTIONS"])
def product_detail(request: HttpRequest, product_id: int) -> HttpResponse:
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
            product.sku = body.get("sku", product.sku)
            product.save()

            # Update or create inventory if store_id is provided
            inventory_data = None
            if "store_id" in body:
                try:
                    store = Store.objects.get(id=body["store_id"])
                except Store.DoesNotExist:
                    response["message"] = "Store not found."
                    return JsonResponse(response, status=400)

                # Get or create inventory entry for this product and store
                inventory, created = Inventory.objects.get_or_create(
                    product=product,
                    store=store,
                    defaults={
                        'quantity': body.get("quantity", 0),
                        'min_stock': body.get("min_stock", 0),
                    }
                )

                # If inventory exists and we have new values, update them
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

            total_stock = sum(item.quantity for item in product.inventory_items.all())
            response["status"] = "success"
            response_data = {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "category": product.get_category_display(),
                "price": str(product.price),
                "sku": product.sku,
                "total_stock": total_stock,
            }

            # Add inventory data if it was updated
            if inventory_data:
                response_data["inventory"] = inventory_data

            response["data"] = response_data

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
