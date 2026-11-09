from typing import Protocol


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
