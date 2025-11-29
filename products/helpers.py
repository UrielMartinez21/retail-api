# Django imports
from django.db.models import Q
from django.http import HttpRequest
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def get_query_params(request: HttpRequest) -> dict:
    """Extract and return query parameters from the request."""
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
    """Build and return query filters based on the provided parameters."""
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


def build_pagination_params(filtered_products, page: int, page_size: int) -> tuple:
    """Extract and return pagination parameters."""
    paginator = Paginator(filtered_products, page_size)
    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = []

    return paginator, products_page
