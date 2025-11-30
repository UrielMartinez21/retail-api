# Django imports
from django.db.models import Q
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.core.exceptions import ValidationError

# Local imports
from products.models import Product, Store, Inventory, Movement

# Standard library imports
from typing import Tuple


# Constants
REQUIRED_FIELDS = ["product_id", "source_store_id", "target_store_id", "quantity"]


def get_query_params(request: HttpRequest) -> dict:
    """Extract and validate query parameters from HTTP request for product filtering.

    This function processes query parameters commonly used for product filtering
    such as category, price range, stock status, and pagination parameters.

    Args:
        request (HttpRequest): The HTTP request object containing query parameters

    Returns:
        dict: Dictionary containing extracted parameters with the following keys:
            - category (str | None): Product category filter
            - min_price (str | None): Minimum price filter
            - max_price (str | None): Maximum price filter
            - in_stock (str | None): Stock availability filter ("true"/"false")
            - page (str): Page number for pagination (default: "1")
            - page_size (str): Number of items per page (default: "10")
    """

    category = request.GET.get("category")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    in_stock = request.GET.get("in_stock")
    page = request.GET.get("page", 1)
    page_size = request.GET.get("page_size", 10)

    return {
        "category": category,
        "min_price": min_price,
        "max_price": max_price,
        "in_stock": in_stock,
        "page": page,
        "page_size": page_size,
    }


def build_filters(params: dict) -> Q:
    """Build Django Q object filters for product queries based on provided parameters.

    Constructs complex database query filters using Django's Q objects for
    product filtering by category, price range, and inventory status.

    Args:
        params (dict): Dictionary containing filter parameters with keys:
            - category (str | None): Filter by product category
            - min_price (str | None): Minimum price threshold
            - max_price (str | None): Maximum price threshold
            - in_stock (str | None): Stock filter ("true"/"false"/"")

    Returns:
        Q: Django Q object containing combined filters for database query.
        Returns empty Q() if no valid filters provided.
    """
    filters = Q()
    if params["category"]:
        filters &= Q(category=params["category"])
    if params["min_price"]:
        filters &= Q(price__gte=params["min_price"])
    if params["max_price"]:
        filters &= Q(price__lte=params["max_price"])
    if params["in_stock"] is not None:
        if params["in_stock"].lower() == "true":
            filters &= Q(inventory_items__quantity__gt=0)
        elif params["in_stock"].lower() == "false":
            filters &= Q(inventory_items__quantity=0)
    return filters


def build_response(status: str, status_code:int, message: str = "", data: dict = None) -> JsonResponse:
    """Build standardized JSON response for API endpoints.

    Creates consistent JSON responses following a standard structure for
    all API endpoints in the application. Ensures uniform error handling
    and success response formatting.

    Args:
        params (dict): Dictionary containing response parameters:
            - status (str): Response status indicator ("success", "error", "warning")
            - status_code (int): HTTP status code (200, 400, 404, 500, etc.)
            - message (str, optional): Human-readable message describing the response.
            - data (dict | None, optional): Response payload containing actual data.

    Returns:
        JsonResponse: Django JsonResponse object with standardized structure:
            {
                "status": str,
                "message": str,
                "data": dict | None
            }
    """
    return JsonResponse(
        {"status": status, "message": message, "data": data}, status=status_code
    )


def validate_request_body(body: dict) -> None:
    """Validate the request body for required fields and quantity.

    This function ensures that the incoming request body contains all the
    necessary fields and that their values meet the expected criteria.

    Validation checks include:
        - Presence of all required fields: 'product_id', 'source_store_id',
        'target_store_id', and 'quantity'.
        - The 'quantity' field must be a positive integer.
        - The 'source_store_id' and 'target_store_id' must be different.

    Args:
        body (dict): The request body to validate. Expected keys are:
            - product_id (int): ID of the product to transfer.
            - source_store_id (int): ID of the source store.
            - target_store_id (int): ID of the target store.
            - quantity (int): Quantity of the product to transfer.

    Raises:
        ValidationError: If any of the required fields are missing, if the
        quantity is not a positive integer, or if the source and target
        store IDs are the same.
    """
    for field in REQUIRED_FIELDS:
        if field not in body:
            raise ValidationError(f"The field '{field}' is required.")

    quantity = body.get("quantity")
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValidationError("The quantity must be a positive integer.")

    if body["source_store_id"] == body["target_store_id"]:
        raise ValidationError("The origin and destination stores must be different.")


def fetch_product_and_stores(body: dict) -> Tuple[Product, Store, Store]:
    """Fetch the product and stores from the database.

    This function retrieves the product and the source and target stores
    based on the IDs provided in the request body. It ensures that the
    specified product and stores exist in the database.

    Args:
        body (dict): The request body containing the following keys:
            - product_id (int): ID of the product to fetch.
            - source_store_id (int): ID of the source store.
            - target_store_id (int): ID of the target store.

    Returns:
        Tuple[Product, Store, Store]: A tuple containing the fetched product,
        source store, and target store.

    Raises:
        ValidationError: If the product or any of the specified stores do not exist.
    """
    try:
        product = Product.objects.get(id=body["product_id"])
    except Product.DoesNotExist:
        raise ValidationError("Product not found.")

    try:
        source_store = Store.objects.get(id=body["source_store_id"])
        target_store = Store.objects.get(id=body["target_store_id"])
    except Store.DoesNotExist:
        raise ValidationError("One or both stores could not be found.")

    return product, source_store, target_store


def validate_source_inventory(product: Product, source_store: Store, quantity: int) -> Inventory:
    """Validate the source store inventory for sufficient stock.

    This function checks whether the source store has enough inventory
    of the specified product to fulfill the requested quantity. If the
    inventory is insufficient or the product is not available in the
    source store, an appropriate error is raised.

    Args:
        product (Product): The product to validate in the source store.
        source_store (Store): The store from which the product is being transferred.
        quantity (int): The quantity of the product to validate.

    Returns:
        Inventory: The inventory object for the product in the source store.

    Raises:
        ValidationError: If the product is not available in the source store
        or if the available quantity is less than the requested quantity.
    """
    try:
        source_inventory = Inventory.objects.get(product=product, store=source_store)
    except Inventory.DoesNotExist:
        raise ValidationError(
            f"The product '{product.name}' is not available in the store '{source_store.name}'."
        )

    if source_inventory.quantity < quantity:
        raise ValidationError(
            f"Insufficient stock in store '{source_store.name}'. "
            f"Available: {source_inventory.quantity}, Required: {quantity}."
        )

    return source_inventory


def perform_inventory_transfer(
    product: Product, source_store: Store, target_store: Store, quantity: int, source_inventory: Inventory
) -> dict:
    """Perform the inventory transfer and return the response data.

    This function handles the transfer of inventory between two stores. It updates
    the inventory levels for the source and target stores, creates a movement record
    to log the transfer, and returns detailed information about the transfer.

    The operation is performed within a database transaction to ensure consistency.

    Args:
        product (Product): The product being transferred.
        source_store (Store): The store from which the product is being transferred.
        target_store (Store): The store to which the product is being transferred.
        quantity (int): The quantity of the product to transfer.
        source_inventory (Inventory): The inventory object for the product in the source store.

    Returns:
        dict: A dictionary containing details of the transfer, including:
            - transfer_id (int): ID of the movement record.
            - product (dict): Details of the transferred product (id, name, sku).
            - source_store (dict): Details of the source store (id, name, remaining stock).
            - target_store (dict): Details of the target store (id, name, new stock, inventory_created).
            - quantity_transferred (int): The quantity of the product transferred.
            - timestamp (str): ISO 8601 timestamp of the transfer.

    Raises:
        ValidationError: If any validation checks fail during the transfer process.
    """
    with transaction.atomic():
        # Update source inventory (use the passed inventory object)
        source_inventory.quantity -= quantity
        source_inventory.save()

        # Get or create target inventory
        target_inventory, created = Inventory.objects.get_or_create(
            product=product,
            store=target_store,
            defaults={"quantity": 0, "min_stock": 0},
        )
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

    # Build response data
    return {
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
