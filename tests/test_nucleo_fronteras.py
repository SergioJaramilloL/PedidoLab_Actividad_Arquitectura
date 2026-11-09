"""Pruebas del núcleo a través de sus puertos.

Demuestran que ServicioPedidos procesa un pedido conociendo solo contratos
(puertos de entrada y de salida), sin depender de StockCloudAPI ni de ningún
otro detalle externo.
"""

import ast
from pathlib import Path

import pytest

from pedidolabs.servicio_pedidos import ServicioPedidos
from pedidolabs.solicitudes import LineaSolicitud, SolicitudPedido

RUTA_SERVICIO = Path(__file__).resolve().parents[1] / "src" / "pedidolabs" / "servicio_pedidos.py"


class InventarioFake:
    """Implementa el puerto InventarioPedidos sin ningún proveedor real."""

    def __init__(self):
        self.reservas = []

    def validar_disponibilidad(self, codigo, cantidad):
        return True

    def reservar(self, codigo, cantidad):
        self.reservas.append((codigo, cantidad))


class RepositorioFake:
    def __init__(self):
        self.guardados = []

    def guardar(self, pedido):
        self.guardados.append(pedido)


class PagoFake:
    def cobrar(self, numero_tarjeta, monto):
        return "TX-FAKE"


class NotificadorFake:
    def __init__(self):
        self.eventos = []

    def pago_recibido(self, cliente, pedido_id, transaccion_id, total):
        self.eventos.append("pago_recibido")

    def pedido_confirmado(self, cliente, pedido_id, total):
        self.eventos.append("pedido_confirmado")


def solicitud_de_prueba(**cambios):
    datos = dict(
        pedido_id="P-100", documento="10", nombre="Ana", email="ana@test.com",
        telefono="300", tipo_cliente="NORMAL", calle="Calle 1", ciudad="Manizales",
        departamento="Caldas", codigo_postal="170001",
        items=(LineaSolicitud("A", "Producto A", 100_000, 1.0, 2),),
        numero_tarjeta="4111111111111111", enviar_confirmacion=True,
    )
    datos.update(cambios)
    return SolicitudPedido(**datos)


def test_nucleo_procesa_solicitud_solo_con_puertos_y_fakes():
    inventario, repo, notif = InventarioFake(), RepositorioFake(), NotificadorFake()
    servicio = ServicioPedidos(inventario, repo, PagoFake(), notif)

    pedido = servicio.procesar(solicitud_de_prueba())

    assert pedido.estado == "CONFIRMADO"
    assert pedido.transaccion_id == "TX-FAKE"
    assert inventario.reservas == [("A", 2)]
    assert repo.guardados == [pedido]
    assert notif.eventos == ["pago_recibido", "pedido_confirmado"]


def test_reglas_de_negocio_siguen_en_el_nucleo_y_no_en_las_entradas():
    """Pedido sin items: la regla la aplica el caso de uso, venga de donde venga."""
    servicio = ServicioPedidos(InventarioFake(), RepositorioFake(), PagoFake(), NotificadorFake())
    with pytest.raises(ValueError, match="al menos un producto"):
        servicio.procesar(solicitud_de_prueba(items=()))
