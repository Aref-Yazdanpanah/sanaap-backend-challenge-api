import django_filters

from .models import Document


class DocumentFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr="icontains")
    content_type = django_filters.CharFilter(lookup_expr="iexact")
    owner = django_filters.NumberFilter(field_name="owner_id")
    created_from = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_to = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    updated_from = django_filters.IsoDateTimeFilter(
        field_name="updated_at", lookup_expr="gte"
    )
    updated_to = django_filters.IsoDateTimeFilter(
        field_name="updated_at", lookup_expr="lte"
    )

    class Meta:
        model = Document
        fields = (
            "title",
            "content_type",
            "owner",
            "status",
            "created_from",
            "created_to",
            "updated_from",
            "updated_to",
        )
