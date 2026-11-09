"""Adapter de entrada REST simulado (sin framework web).

Representa un endpoint POST /pedidos: recibe un cuerpo ya decodificado (dict),
lo traduce al comando, invoca el puerto de entrada y traduce el resultado a una
respuesta con código HTTP. No calcula, no reserva, no cobra, no persiste.
"""

from ..puertos import ProcesarPedido
from .mapeo import SolicitudInvalida, solicitud_desde_dict


class ControladorPedidosREST:

    def __init__(self, caso_uso: ProcesarPedido):
        self.caso_uso = caso_uso

    def post_pedidos(self, cuerpo) -> dict:
        try:
            solicitud = solicitud_desde_dict(cuerpo)
        except SolicitudInvalida as error:
            return _respuesta(400, {"error": str(error)})

        try:
            pedido = self.caso_uso.procesar(solicitud)
        except ValueError as error:
            # Regla de negocio incumplida (stock, tarjeta, pedido vacío...).
            return _respuesta(422, {"error": str(error)})
        except RuntimeError as error:
            # Falla de un proveedor externo (pago rechazado, inventario remoto...).
            return _respuesta(502, {"error": str(error)})

        return _respuesta(201, {
            "pedido_id": pedido.id,
            "estado": pedido.estado,
            "total_pagado": pedido.total_pagado,
            "transaccion_id": pedido.transaccion_id,
        })


def _respuesta(status: int, cuerpo: dict) -> dict:
    return {"status": status, "body": cuerpo}
