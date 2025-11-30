# Django imports
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

# Local imports
from .models import Store, Inventory, Movement
from .handles import (
    handle_get_products, handle_post_product,
    handle_get_product, handle_put_product, handle_delete_product,
    
)
from .helpers import build_response, fetch_product_and_stores, perform_inventory_transfer, validate_request_body, validate_source_inventory

# Standard library imports
import json
import logging

# Logger for this module
logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def products(request: HttpRequest) -> HttpResponse:
    """Handle requests for the products endpoint."""
    
    log_id = getattr(request, 'log_id', 'unknown')
    
    logger.info(
        "Products endpoint accessed",
        extra={
            'log_id': log_id,
            'endpoint': 'products',
            'method': request.method,
            'event_type': 'endpoint_access'
        }
    )

    if request.method == "OPTIONS":
        logger.debug(
            "OPTIONS request handled",
            extra={
                'log_id': log_id,
                'endpoint': 'products',
                'event_type': 'options_request'
            }
        )
        return build_response("success", 200)

    if request.method == "GET":
        logger.info(
            "Processing GET products request",
            extra={
                'log_id': log_id,
                'endpoint': 'products',
                'event_type': 'get_products'
            }
        )
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
@require_http_methods(["GET", "POST", "OPTIONS"])
def stores(request: HttpRequest) -> HttpResponse:
    """List all stores or create a new store."""

    try:
        if request.method == "OPTIONS":
            return build_response("success", 200)

        elif request.method == "GET":
            stores = Store.objects.only("id", "name", "address")

            if not stores.exists():
                return build_response("error", 404, message="No stores found.")

            store_list = [
                {"id": store.id, "name": store.name, "address": store.address}
                for store in stores
            ]

            return build_response("success", 200, data={"stores": store_list})
        elif request.method == "POST":
            body = json.loads(request.body)
            name = body.get("name")
            address = body.get("address")

            if not name or not address:
                return build_response("error", 400, message="Name and address are required.")

            store = Store.objects.create(name=name, address=address)

            return build_response(
                "success",
                200,
                message="Store created successfully.",
                data={"store": {"id": store.id, "name": store.name, "address": store.address}}
            )
    except Exception as e:
        return build_response("error", 500, message=str(e))


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

            # Validate request body
            validate_request_body(body)

            # Fetch product and stores
            product, source_store, target_store = fetch_product_and_stores(body)

            # Validate source inventory
            source_inventory = validate_source_inventory(
                product, source_store, body["quantity"]
            )

            # Perform transfer
            response_data = perform_inventory_transfer(
                product, source_store, target_store, body["quantity"], source_inventory
            )

            return build_response(
                "success", 200, message="Transfer completed successfully.", data=response_data
            )

    except json.JSONDecodeError:
        return build_response("error", 400, message="Invalid JSON in request body.")
    except ValidationError as e:
        return build_response("error", 400, message=str(e))
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