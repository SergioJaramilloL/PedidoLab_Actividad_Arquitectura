"""Pruebas de la frontera de inventario remoto.

Demuestran que StockCloud queda detrás de un adapter: el adapter es quien
interpreta query_stock / reserve_units y sus códigos, y los traduce al
contrato del puerto InventarioPedidos (True / None / ValueError / RuntimeError).
"""

import pytest

from pedidolabs.inventario import Inventario
from pedidolabs.inventario_stockcloud import AdaptadorStockCloud
from pedidolabs.stockcloud_api import StockCloudAPI


class StockCloudGrabador:
    """Doble de la API de StockCloud que registra cada llamada recibida."""

    def __init__(self, respuesta_query, respuesta_reserva=None):
        self.respuesta_query = respuesta_query
        self.respuesta_reserva = respuesta_reserva
        self.llamadas = []

    def query_stock(self, sku):
        self.llamadas.append(("query_stock", sku))
        return self.respuesta_query

    def reserve_units(self, sku, units):
        self.llamadas.append(("reserve_units", sku, units))
        return self.respuesta_reserva


def test_adapter_traduce_metodos_del_puerto_a_la_api_de_stockcloud():
    api = StockCloudGrabador(
        respuesta_query={"status": "OK", "sku": "A", "available_units": 5},
        respuesta_reserva={"status": "RESERVED", "sku": "A", "remaining_units": 3},
    )
    adaptador = AdaptadorStockCloud(api)

    assert adaptador.validar_disponibilidad("A", 2) is True
    adaptador.reservar("A", 2)

    # El vocabulario de PedidoLab (validar/reservar) se tradujo al de StockCloud.
    assert api.llamadas == [("query_stock", "A"), ("reserve_units", "A", 2)]


@pytest.mark.parametrize(
    "respuesta, mensaje",
    [
        ({"status": "NOT_FOUND", "sku": "Z", "available_units": 0}, "no existe"),
        ({"status": "OK", "sku": "Z", "available_units": 1}, "Stock insuficiente"),
    ],
)
def test_codigos_de_consulta_se_traducen_al_contrato_de_errores_del_puerto(respuesta, mensaje):
    adaptador = AdaptadorStockCloud(StockCloudGrabador(respuesta_query=respuesta))
    with pytest.raises(ValueError, match=mensaje):
        adaptador.validar_disponibilidad("Z", 3)


@pytest.mark.parametrize(
    "respuesta, mensaje",
    [
        ({"status": "NOT_FOUND", "sku": "Z"}, "no existe"),
        ({"status": "INSUFFICIENT_STOCK", "sku": "Z", "available_units": 1,
          "requested_units": 3}, "Stock insuficiente"),
        ({"status": "INVALID_UNITS", "sku": "Z"}, "positiva"),
    ],
)
def test_codigos_de_reserva_se_traducen_al_contrato_de_errores_del_puerto(respuesta, mensaje):
    adaptador = AdaptadorStockCloud(StockCloudGrabador({}, respuesta_reserva=respuesta))
    with pytest.raises(ValueError, match=mensaje):
        adaptador.reservar("Z", 3)


def test_codigo_desconocido_de_stockcloud_es_falla_tecnica_no_de_negocio():
    adaptador = AdaptadorStockCloud(
        StockCloudGrabador({"status": "MAINTENANCE"}, {"status": "MAINTENANCE"})
    )
    with pytest.raises(RuntimeError, match="MAINTENANCE"):
        adaptador.validar_disponibilidad("A", 1)
    with pytest.raises(RuntimeError, match="MAINTENANCE"):
        adaptador.reservar("A", 1)


@pytest.mark.parametrize("crear_inventario", [
    lambda: Inventario({"A": 3}),
    lambda: AdaptadorStockCloud(StockCloudAPI({"A": 3})),
], ids=["local", "stockcloud"])
def test_local_y_stockcloud_cumplen_el_mismo_contrato_observable(crear_inventario):
    """Sustituibilidad: con cualquiera de los dos, el núcleo ve el mismo comportamiento."""
    inventario = crear_inventario()

    assert inventario.validar_disponibilidad("A", 3) is True
    inventario.reservar("A", 2)
    with pytest.raises(ValueError, match="Stock insuficiente"):
        inventario.validar_disponibilidad("A", 2)
    with pytest.raises(ValueError, match="no existe"):
        inventario.validar_disponibilidad("Z", 1)
    with pytest.raises(ValueError, match="positiva"):
        inventario.validar_disponibilidad("A", 0)
