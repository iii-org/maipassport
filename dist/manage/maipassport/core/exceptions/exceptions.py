from django.utils.translation import ugettext_lazy as _
from rest_framework import status, serializers
from rest_framework.exceptions import ErrorDetail


def FieldValidationError(field, message, code, is_non_field_errors=False):
    """
    Generate validation error format compatible with serializers.validators
    while raising error in serializer.create and serializer.update.
    """
    if is_non_field_errors:
        return serializers.ValidationError({
            field: [{'non_field_errors': [ErrorDetail(message, code=code)]}]
        })
    else:
        return serializers.ValidationError({
            field: [ErrorDetail(message, code=code)]
        })


def NonFieldValidationError(message, code):
    """
    Generate validation error format compatible with serializers.validate
    while raising error in serializer.create and serializer.update.
    """
    return serializers.ValidationError({
        'non_field_errors': [ErrorDetail(message, code=code)]
    })
