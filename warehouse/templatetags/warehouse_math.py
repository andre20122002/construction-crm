from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter(name='abs_value')
def abs_value(value):
    """
    Повертає модуль числа (absolute value).
    Працює з Decimal, int, float, str.
    Якщо значення None або не може бути перетворено в число — повертає 0.
    """
    if value is None:
        return 0

    try:
        # Конвертуємо в Decimal через рядок для максимальної сумісності та точності
        # Це покриває int, float, str та власне Decimal
        val = Decimal(str(value))
        return abs(val)
    except (ValueError, TypeError, InvalidOperation):
        return 0