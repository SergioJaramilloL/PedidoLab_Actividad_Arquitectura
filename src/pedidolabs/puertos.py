from typing import Protocol

from .solicitudes import SolicitudPedido


class RepositorioPedidos(Protocol):

    def guardar(self, pedido) -> None:
        ...


class ProcesadorPago(Protocol):
    """Puerto de salida: la aplicación necesita cobrar, no conocer PayFast."""

    def cobrar(self, numero_tarjeta: str, monto: float) -> str:
        ...


class NotificadorPedidos(Protocol):
    """Puerto de salida: la aplicación expresa eventos de negocio, no canales concretos."""

    def pago_recibido(self, cliente, pedido_id: str, transaccion_id: str, total: float) -> None:
        ...

    def pedido_confirmado(self, cliente, pedido_id: str, total: float) -> None:
        ...


class InventarioPedidos(Protocol):
    """Puerto de salida: la aplicación necesita validar y reservar stock,
    no conocer quién lo administra (inventario local, StockCloud, ...).

    Contrato de errores: si no hay disponibilidad o el producto no existe,
    la implementación lanza ValueError. Fallas técnicas del proveedor: RuntimeError.
    Solo expone las dos capacidades que el caso de uso usa.
    """

    def validar_disponibilidad(self, codigo: str, cantidad: int) -> bool:
        ...

    def reservar(self, codigo: str, cantidad: int) -> None:
        ...


class ProcesarPedido(Protocol):
    """Puerto de entrada: capacidad que la aplicación ofrece a sus canales
    (REST, batch, CLI...). Los adapters de entrada dependen de este contrato,
    no de ServicioPedidos ni de su firma de 13 parámetros.
    """

    def procesar(self, solicitud: SolicitudPedido):
        ...
