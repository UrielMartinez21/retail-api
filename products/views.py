# Django imports
from django.db import transaction, models
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

# Local imports
from .models import Product, Store, Inventory, Movement
from .handles import (
    handle_get_products, handle_post_product,
    handle_get_product, handle_put_product, handle_delete_product
)
from .helpers import build_response

# Standard library imports
import json


@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def products(request: HttpRequest) -> HttpResponse:
    """Handle requests for the products endpoint."""

    if request.method == "OPTIONS":
        return build_response("success", 200)

    if request.method == "GET":
        return handle_get_products(request)

    if request.method == "POST":
        return handle_post_product(request)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE", "OPTIONS"])
def product_detail(request: HttpRequest, product_id: int) -> HttpResponse:
    """Handle requests for a specific product."""

    if request.method == "OPTIONS":
        return build_response("success", 200)

    if request.method == "GET":
        return handle_get_product(product_id)

    if request.method == "PUT":
        return handle_put_product(request, product_id)

    if request.method == "DELETE":
        return handle_delete_product(product_id)


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def store_inventory(request: HttpRequest, store_id: int) -> HttpResponse:
    """List inventory for a specific store."""

    try:
        if request.method == "OPTIONS":
            return build_response("success", 200)

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

            return build_response("success", 200, data={"inventory": inventory_list})
    except Exception as e:
        return build_response("error", 500, message=str(e))


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def transfer_inventory(request: HttpRequest) -> HttpResponse:
    """Transfer products between stores with stock validation."""

    try:
        if request.method == "OPTIONS":
            return build_response("success", 200)

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
                    return build_response("error", 400, message=f"The field '{field}' is required.")

            # Validate quantity is positive
            quantity = body["quantity"]
            if not isinstance(quantity, int) or quantity <= 0:
                return build_response("error", 400, message="The quantity must be a positive integer.")

            # Validate stores are different
            if body["source_store_id"] == body["target_store_id"]:
                return build_response("error", 400, message="The origin and destination stores must be different.")

            # Get product
            try:
                product = Product.objects.get(id=body["product_id"])
            except Product.DoesNotExist:
                return build_response("error", 404, message="Product not found.")

            # Get stores
            try:
                source_store = Store.objects.get(id=body["source_store_id"])
                target_store = Store.objects.get(id=body["target_store_id"])
            except Store.DoesNotExist:
                return build_response("error", 404, message="One or both stores could not be found.")

            # Get source inventory
            try:
                source_inventory = Inventory.objects.get(
                    product=product, store=source_store
                )
            except Inventory.DoesNotExist:
                return build_response(
                    "error",
                    400,
                    message=f"The product '{product.name}' is not available in the store '{source_store.name}'.",
                )

            # Validate sufficient stock
            if source_inventory.quantity < quantity:
                return build_response(
                    "error",
                    400,
                    message=(
                        f"Insufficient stock in store '{source_store.name}'. "
                        f"Available: {source_inventory.quantity}, Required: {quantity}."
                    ),
                )

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
            return build_response(
                "success",
                200,
                message="Transfer completed successfully.",
                data={
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
                },
            )

    except json.JSONDecodeError:
        return build_response("error", 400, message="Invalid JSON in request body.")
    except Exception as e:
        return build_response("error", 500, message=str(e))


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def inventory_alerts(request: HttpRequest) -> HttpResponse:
    """List products with low stock alerts."""

    try:
        if request.method == "OPTIONS":
            return build_response("success", 200)
        
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
                    return build_response("error", 404, message="Store not found.")
            
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
            
            return build_response(
                "success",
                200,
                data={
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
            )

    except Exception as e:
        return build_response("error", 500, message=str(e))


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def movements(request: HttpRequest) -> HttpResponse:
    try:
        if request.method == "OPTIONS":
            return build_response("success", 200)

        elif request.method == "GET":
            movements = Movement.objects.select_related(
                "product", "source_store", "target_store"
            ).order_by("-timestamp")

            movements_list = []
            for movement in movements:
                movements_list.append(
                    {
                        "id": movement.id,
                        "product": {
                            "id": movement.product.id,
                            "name": movement.product.name,
                            "sku": movement.product.sku,
                        },
                        "type": movement.type,
                        "quantity": movement.quantity,
                        "source_store": {
                            "id": movement.source_store.id,
                            "name": movement.source_store.name,
                        }
                        if movement.source_store
                        else None,
                        "target_store": {
                            "id": movement.target_store.id,
                            "name": movement.target_store.name,
                        }
                        if movement.target_store
                        else None,
                        "timestamp": movement.timestamp.isoformat(),
                    }
                )

            return build_response(
                "success",
                200,
                data={"movements": movements_list}
            )

    except Exception as e:
        return build_response("error", 500, message=str(e))