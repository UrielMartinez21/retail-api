# Django imports
from django.db import transaction, models
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

# Local imports
from .models import Product, Store, Inventory, Movement
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
            filtered_products = (
                Product.objects.filter(filters)
                .prefetch_related("inventory_items")
                .distinct()
            )

            # Build pagination
            paginator, products_page = build_pagination_params(
                filtered_products, int(params["page"]), int(params["page_size"])
            )

            # Build the products list
            products_list = []
            for product in products_page:
                total_stock = sum(
                    item.quantity for item in product.inventory_items.all()
                )
                products_list.append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description,
                        "category": product.get_category_display(),
                        "price": str(product.price),
                        "sku": product.sku,
                        "total_stock": total_stock,
                    }
                )

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
            product = Product.objects.prefetch_related("inventory_items").get(id=product_id)
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
                    response["message"] = "Store not found."
                    return JsonResponse(response, status=400)

                # Get or create inventory entry for this product and store
                inventory, created = Inventory.objects.get_or_create(
                    product=product,
                    store=store,
                    defaults={
                        "quantity": body.get("quantity", 0),
                        "min_stock": body.get("min_stock", 0),
                    },
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


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def store_inventory(request: HttpRequest, store_id: int) -> HttpResponse:
    response = {"status": "error", "message": "", "data": None}
    try:
        if request.method == "OPTIONS":
            response["status"] = "success"

        elif request.method == "GET":
            inventories = Inventory.objects.filter(store__id=store_id).select_related("product", "store")
            inventory_list = []
            for inventory in inventories:
                inventory_list.append(
                    {
                        "id": inventory.id,
                        "product_id": inventory.product.id,
                        "store_id": inventory.store.id,
                        "quantity": inventory.quantity,
                        "min_stock": inventory.min_stock,
                    }
                )

            response["status"] = "success"
            response["data"] = {"inventory": inventory_list}

        return JsonResponse(response, status=200)
    except Exception as e:
        response["message"] = str(e)
        return JsonResponse(response, status=500)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def transfer_inventory(request: HttpRequest) -> HttpResponse:
    """Transfer products between stores with stock validation.

    Required fields:
        - product_id: ID of the product to transfer
        - source_store_id: ID of the source store
        - target_store_id: ID of the target store
        - quantity: Amount to transfer

    Returns:
        JsonResponse with transfer details and updated inventory
    """
    response = {"status": "error", "message": "", "data": None}

    try:
        if request.method == "OPTIONS":
            response["status"] = "success"
            return JsonResponse(response, status=200)

        elif request.method == "POST":
            body = json.loads(request.body)

            # Validate required fields
            required_fields = [
                "product_id",
                "source_store_id",
                "target_store_id",
                "quantity",
            ]
            for field in required_fields:
                if field not in body:
                    response["message"] = f"The field'{field}' is required."
                    return JsonResponse(response, status=400)

            # Validate quantity is positive
            quantity = body["quantity"]
            if not isinstance(quantity, int) or quantity <= 0:
                response["message"] = "The quantity must be a positive integer."
                return JsonResponse(response, status=400)

            # Validate stores are different
            if body["source_store_id"] == body["target_store_id"]:
                response["message"] = (
                    "The origin and destination stores must be different."
                )
                return JsonResponse(response, status=400)

            # Get product
            try:
                product = Product.objects.get(id=body["product_id"])
            except Product.DoesNotExist:
                response["message"] = "Product not found."
                return JsonResponse(response, status=404)

            # Get stores
            try:
                source_store = Store.objects.get(id=body["source_store_id"])
                target_store = Store.objects.get(id=body["target_store_id"])
            except Store.DoesNotExist:
                response["message"] = "One or both stores could not be found."
                return JsonResponse(response, status=404)

            # Get source inventory
            try:
                source_inventory = Inventory.objects.get(
                    product=product, store=source_store
                )
            except Inventory.DoesNotExist:
                response["message"] = (
                    f"The product is out of stock '{product.name}' in the store '{source_store.name}'."
                )
                return JsonResponse(response, status=400)

            # Validate sufficient stock
            if source_inventory.quantity < quantity:
                response["message"] = (
                    f"Insufficient stock. Available: {source_inventory.quantity}, Required: {quantity}."
                )
                return JsonResponse(response, status=400)

            # Perform transfer using transaction for data integrity
            with transaction.atomic():
                # Update source inventory
                source_inventory.quantity -= quantity
                source_inventory.save()

                # Get or create target inventory
                target_inventory, created = Inventory.objects.get_or_create(
                    product=product,
                    store=target_store,
                    defaults={"quantity": 0, "min_stock": 0},
                )

                # Update target inventory
                target_inventory.quantity += quantity
                target_inventory.save()

                # Create movement record
                movement = Movement.objects.create(
                    product=product,
                    source_store=source_store,
                    target_store=target_store,
                    quantity=quantity,
                    type="TRANSFER",
                )

            # Build response
            response["status"] = "success"
            response["message"] = "Transfer completed successfully."
            response["data"] = {
                "transfer_id": movement.id,
                "product": {"id": product.id, "name": product.name, "sku": product.sku},
                "source_store": {
                    "id": source_store.id,
                    "name": source_store.name,
                    "remaining_stock": source_inventory.quantity,
                },
                "target_store": {
                    "id": target_store.id,
                    "name": target_store.name,
                    "new_stock": target_inventory.quantity,
                    "inventory_created": created,
                },
                "quantity_transferred": quantity,
                "timestamp": movement.timestamp.isoformat(),
            }

            return JsonResponse(response, status=200)

    except json.JSONDecodeError:
        response["message"] = "JSON inválido en el cuerpo de la solicitud."
        return JsonResponse(response, status=400)
    except Exception as e:
        response["message"] = f"Error interno del servidor: {str(e)}"
        return JsonResponse(response, status=500)


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def inventory_alerts(request: HttpRequest) -> HttpResponse:
    """List products with low stock alerts.
    
    Returns products where inventory quantity is less than or equal to min_stock.
    Supports filtering by store_id via query parameter.
    
    Query Parameters:
        store_id (optional): Filter alerts for specific store
    
    Returns:
        JsonResponse with list of low stock products
    """
    response = {"status": "error", "message": "", "data": None}
    
    try:
        if request.method == "OPTIONS":
            response["status"] = "success"
            return JsonResponse(response, status=200)
        
        elif request.method == "GET":
            # Get optional store filter
            store_id = request.GET.get('store_id')
            
            # Build base query for low stock items
            low_stock_query = Inventory.objects.filter(
                quantity__lte=models.F('min_stock')
            ).select_related('product', 'store')
            
            # Apply store filter if provided
            if store_id:
                try:
                    store = Store.objects.get(id=store_id)
                    low_stock_query = low_stock_query.filter(store=store)
                except Store.DoesNotExist:
                    response["message"] = "Store not found."
                    return JsonResponse(response, status=404)
            
            # Get low stock items
            low_stock_items = low_stock_query.order_by('product__name', 'store__name')
            
            # Build alerts list
            alerts_list = []
            for item in low_stock_items:
                alert = {
                    "inventory_id": item.id,
                    "product": {
                        "id": item.product.id,
                        "name": item.product.name,
                        "sku": item.product.sku,
                        "category": item.product.get_category_display()
                    },
                    "store": {
                        "id": item.store.id,
                        "name": item.store.name,
                        "address": item.store.address
                    },
                    "current_stock": item.quantity,
                    "min_stock": item.min_stock,
                    "deficit": item.min_stock - item.quantity,
                    "alert_level": "critical" if item.quantity == 0 else "warning"
                }
                alerts_list.append(alert)
            
            # Group statistics
            total_alerts = len(alerts_list)
            critical_alerts = len([alert for alert in alerts_list if alert["alert_level"] == "critical"])
            warning_alerts = total_alerts - critical_alerts
            
            response["status"] = "success"
            response["data"] = {
                "alerts": alerts_list,
                "summary": {
                    "total_alerts": total_alerts,
                    "critical_alerts": critical_alerts,
                    "warning_alerts": warning_alerts
                },
                "filter_applied": {
                    "store_id": store_id if store_id else None
                }
            }
            
            return JsonResponse(response, status=200)
    
    except Exception as e:
        response["message"] = f"Error interno del servidor: {str(e)}"
        return JsonResponse(response, status=500)