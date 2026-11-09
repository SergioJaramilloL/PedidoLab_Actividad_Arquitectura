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


# --- Independencia estática y ensamblaje real --------------------------------

def test_servicio_pedidos_no_importa_stockcloud_ni_infraestructura():
    """Restricción 3 verificada automáticamente: el núcleo no conoce detalles externos."""
    arbol = ast.parse(RUTA_SERVICIO.read_text(encoding="utf-8"))
    importados = {
        segmento
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
        for segmento in nodo.module.split(".")
    }
    nombres = {
        alias.name
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom)
        for alias in nodo.names
    }
    detalles = {"stockcloud_api", "inventario_stockcloud", "inventario",
                "pagos", "repositorio", "notificaciones", "entrada"}
    assert importados.isdisjoint(detalles), importados
    assert "StockCloudAPI" not in nombres
    assert "StockCloudAPI" not in RUTA_SERVICIO.read_text(encoding="utf-8")


@pytest.mark.parametrize("proveedor", ["local", "stockcloud"])
def test_mismo_caso_de_uso_procesa_pedidos_con_inventario_local_o_stockcloud(tmp_path, proveedor):
    from pedidolabs.bootstrap import crear_aplicacion
    from pedidolabs.notificaciones import limpiar_bandeja

    limpiar_bandeja()
    app = crear_aplicacion(proveedor, {"A": 10}, tmp_path / "pedidos.jsonl")

    pedido = app.servicio.procesar(solicitud_de_prueba())

    assert pedido.estado == "CONFIRMADO"
    # El servicio es el mismo tipo en ambos despliegues; solo cambió el adapter inyectado.
    assert type(app.servicio) is ServicioPedidos
    assert app.servicio.inventario.validar_disponibilidad("A", 8) is True
    with pytest.raises(ValueError, match="Stock insuficiente"):
        app.servicio.inventario.validar_disponibilidad("A", 9)


def test_composition_root_conecta_ambas_entradas_a_la_misma_instancia_del_caso_de_uso(tmp_path):
    from pedidolabs.bootstrap import crear_aplicacion

    app = crear_aplicacion("stockcloud", {"A": 10}, tmp_path / "pedidos.jsonl")

    assert app.rest.caso_uso is app.servicio
    assert app.batch.caso_uso is app.servicio


def test_flujo_completo_rest_y_batch_con_stockcloud_detras_del_adapter(tmp_path):
    from pedidolabs.bootstrap import crear_aplicacion
    from pedidolabs.inventario_stockcloud import AdaptadorStockCloud
    from pedidolabs.notificaciones import limpiar_bandeja
    from pedidolabs.repositorio import RepositorioArchivo

    limpiar_bandeja()
    ruta = tmp_path / "pedidos.jsonl"
    app = crear_aplicacion("stockcloud", {"A": 5}, ruta)
    cuerpo = {
        "pedido_id": "P-100", "documento": "10", "nombre": "Ana",
        "email": "ana@test.com", "telefono": "300", "tipo_cliente": "NORMAL",
        "calle": "Calle 1", "ciudad": "Manizales", "departamento": "Caldas",
        "codigo_postal": "170001",
        "items": [{"codigo": "A", "nombre": "Producto A", "precio": 100000,
                   "peso": 1.0, "cantidad": 2}],
        "numero_tarjeta": "4111111111111111", "enviar_confirmacion": True,
    }

    respuesta = app.rest.post_pedidos(cuerpo)
    lote = app.batch.ejecutar([dict(cuerpo, pedido_id="P-101"),
                               dict(cuerpo, pedido_id="P-102")])

    assert isinstance(app.servicio.inventario, AdaptadorStockCloud)
    assert respuesta["status"] == 201
    assert lote.procesados == ["P-101"]  # 2 + 2 unidades; la tercera solicitud excede el stock
    assert "Stock insuficiente" in lote.fallidos[0][1]
    assert [r["id"] for r in RepositorioArchivo(ruta).listar()] == ["P-100", "P-101"]


def test_proveedor_desconocido_falla_en_el_composition_root():
    from pedidolabs.bootstrap import crear_inventario
    with pytest.raises(ValueError, match="no soportado"):
        crear_inventario("otro")
