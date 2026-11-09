"""Adapter de salida para el proveedor de inventario StockCloud.

Implementa el puerto InventarioPedidos traduciendo al contrato de StockCloudAPI
(query_stock / reserve_units con respuestas en diccionarios y códigos propios).

Es el único módulo de PedidoLab que conoce los métodos y códigos de StockCloud.
"""

from .stockcloud_api import StockCloudAPI


class AdaptadorStockCloud:
    """Adapter: traduce el puerto InventarioPedidos al contrato de StockCloudAPI."""

    def __init__(self, api: StockCloudAPI):
        # La API se recibe por constructor: crearla es decisión del Composition Root.
        self.api = api

    def validar_disponibilidad(self, codigo: str, cantidad: int) -> bool:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva")

        respuesta = self.api.query_stock(codigo)
        estado = respuesta.get("status")

        if estado == "NOT_FOUND":
            raise ValueError(f"Producto {codigo} no existe en inventario")
        if estado != "OK":
            raise RuntimeError(f"StockCloud respondió un estado inesperado: {estado}")

        disponible = respuesta.get("available_units", 0)
        if disponible < cantidad:
            raise ValueError(
                f"Stock insuficiente para {codigo}: "
                f"disponible={disponible}, solicitado={cantidad}"
            )
        return True

    def reservar(self, codigo: str, cantidad: int) -> None:
        respuesta = self.api.reserve_units(codigo, cantidad)
        estado = respuesta.get("status")

        if estado == "RESERVED":
            return
        if estado == "INVALID_UNITS":
            raise ValueError("La cantidad debe ser positiva")
        if estado == "NOT_FOUND":
            raise ValueError(f"Producto {codigo} no existe en inventario")
        if estado == "INSUFFICIENT_STOCK":
            raise ValueError(
                f"Stock insuficiente para {codigo}: "
                f"disponible={respuesta.get('available_units')}, solicitado={cantidad}"
            )
        raise RuntimeError(f"StockCloud respondió un estado inesperado: {estado}")
