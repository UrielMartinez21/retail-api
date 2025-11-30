# Django imports
from django.db.models import Q
from django.http import HttpRequest, JsonResponse


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


def build_response(status: str, status_code = int, message: str = "", data: dict = None) -> JsonResponse:
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
    return JsonResponse({"status": status, "message": message, "data": data}, status= status_code)

