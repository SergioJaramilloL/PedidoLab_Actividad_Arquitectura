"""Comando de entrada del caso de uso ProcesarPedido.

SolicitudPedido expresa lo que la aplicación necesita para procesar un pedido,
independiente de si llegó por REST, por un lote nocturno o por cualquier otro canal.
Pertenece al núcleo: los adapters de entrada lo construyen; el núcleo lo consume.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class LineaSolicitud:
    codigo: str
    nombre: str
    precio: float
    peso: float
    cantidad: int


@dataclass(frozen=True)
class SolicitudPedido:
    pedido_id: str
    documento: str
    nombre: str
    email: str
    telefono: str
    tipo_cliente: str
    calle: str
    ciudad: str
    departamento: str
    codigo_postal: str
    items: Tuple[LineaSolicitud, ...]
    numero_tarjeta: str
    enviar_confirmacion: bool = True
