from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer

# Количество во входных данных: неотрицательное, до 3 знаков после запятой
Quantity = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]
# В ответах количества отдаём строкой с тремя знаками, чтобы не терять точность
QuantityOut = Annotated[Decimal, PlainSerializer(lambda value: f"{value:.3f}", return_type=str)]
