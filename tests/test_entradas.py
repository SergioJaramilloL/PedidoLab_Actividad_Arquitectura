"""Pruebas de los adapters de entrada (REST simulado y batch).

Demuestran decisiones arquitectónicas:
- Los adapters trabajan contra un FAKE del puerto ProcesarPedido (no necesitan
  inventario, pagos, archivo ni correo).
- Batch y REST reutilizan la misma capacidad y la misma traducción.
- Los adapters no importan infraestructura ni reglas de negocio.
"""

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pedidolabs.entrada.batch import ProcesoBatchPedidos
from pedidolabs.entrada.mapeo import solicitud_desde_dict
from pedidolabs.entrada.rest import ControladorPedidosREST
from pedidolabs.solicitudes import LineaSolicitud, SolicitudPedido

CARPETA_ENTRADA = Path(__file__).resolve().parents[1] / "src" / "pedidolabs" / "entrada"


def pedido_externo(**cambios):
    """Representación externa definida en el enunciado de la actividad."""
    datos = {
        "pedido_id": "P-100", "documento": "10", "nombre": "Ana",
        "email": "ana@test.com", "telefono": "300", "tipo_cliente": "NORMAL",
        "calle": "Calle 1", "ciudad": "Manizales", "departamento": "Caldas",
        "codigo_postal": "170001",
        "items": [{"codigo": "A", "nombre": "Producto A", "precio": 100000,
                   "peso": 1.0, "cantidad": 2}],
        "numero_tarjeta": "4111111111111111", "enviar_confirmacion": True,
    }
    datos.update(cambios)
    return datos


class CasoUsoFake:
    """Fake del puerto de entrada ProcesarPedido: registra solicitudes recibidas."""

    def __init__(self, error=None):
        self.solicitudes = []
        self.error = error

    def procesar(self, solicitud):
        self.solicitudes.append(solicitud)
        if self.error:
            raise self.error
        return SimpleNamespace(
            id=solicitud.pedido_id, estado="CONFIRMADO",
            total_pagado=1.0, transaccion_id="TX-FAKE",
        )


# --- REST ------------------------------------------------------------------

def test_rest_trabaja_contra_un_fake_del_caso_de_uso():
    caso_uso = CasoUsoFake()
    controlador = ControladorPedidosREST(caso_uso)

    respuesta = controlador.post_pedidos(pedido_externo())

    assert respuesta["status"] == 201
    assert respuesta["body"]["pedido_id"] == "P-100"
    # El controller tradujo el dict externo al comando de la aplicación:
    assert len(caso_uso.solicitudes) == 1
    solicitud = caso_uso.solicitudes[0]
    assert isinstance(solicitud, SolicitudPedido)
    assert solicitud.items == (LineaSolicitud("A", "Producto A", 100000.0, 1.0, 2),)


def test_rest_rechaza_forma_invalida_sin_invocar_el_caso_de_uso():
    caso_uso = CasoUsoFake()
    cuerpo = pedido_externo()
    del cuerpo["email"]

    respuesta = ControladorPedidosREST(caso_uso).post_pedidos(cuerpo)

    assert respuesta["status"] == 400
    assert "email" in respuesta["body"]["error"]
    assert caso_uso.solicitudes == []


@pytest.mark.parametrize("error, status", [
    (ValueError("Stock insuficiente para A"), 422),
    (RuntimeError("Pago rechazado: merchant not found"), 502),
])
def test_rest_solo_traduce_errores_del_nucleo_a_codigos_http(error, status):
    respuesta = ControladorPedidosREST(CasoUsoFake(error=error)).post_pedidos(pedido_externo())
    assert respuesta == {"status": status, "body": {"error": str(error)}}


# --- Batch -----------------------------------------------------------------

def test_batch_reutiliza_la_misma_capacidad_y_la_misma_traduccion_que_rest():
    caso_uso = CasoUsoFake()
    lote = [pedido_externo(pedido_id=f"P-{n}") for n in (1, 2, 3)]

    resultado = ProcesoBatchPedidos(caso_uso).ejecutar(lote)
    ControladorPedidosREST(caso_uso).post_pedidos(pedido_externo(pedido_id="P-1"))

    assert resultado.procesados == ["P-1", "P-2", "P-3"]
    # Un único puerto atendió a ambos canales...
    assert [s.pedido_id for s in caso_uso.solicitudes] == ["P-1", "P-2", "P-3", "P-1"]
    # ...y el mismo dict produce el mismo comando por cualquier entrada.
    assert caso_uso.solicitudes[0] == caso_uso.solicitudes[3]


def test_batch_registra_fallos_y_continua_con_el_lote():
    class CasoUsoQueRechazaP2(CasoUsoFake):
        def procesar(self, solicitud):
            if solicitud.pedido_id == "P-2":
                raise ValueError("Stock insuficiente para A")
            return super().procesar(solicitud)

    items_mal_formados = pedido_externo(pedido_id="P-3", items="no-es-lista")
    lote = [pedido_externo(pedido_id="P-1"), pedido_externo(pedido_id="P-2"),
            items_mal_formados, pedido_externo(pedido_id="P-4")]

    resultado = ProcesoBatchPedidos(CasoUsoQueRechazaP2()).ejecutar(lote)

    assert resultado.procesados == ["P-1", "P-4"]
    assert [ident for ident, _ in resultado.fallidos] == ["P-2", "P-3"]
    assert resultado.total == 4


def test_batch_lee_archivo_jsonl_nocturno(tmp_path):
    archivo = tmp_path / "pedidos_noche.jsonl"
    archivo.write_text(
        json.dumps(pedido_externo(pedido_id="N-1")) + "\n"
        + "{esto no es json}\n"
        + json.dumps(pedido_externo(pedido_id="N-2")) + "\n",
        encoding="utf-8",
    )

    resultado = ProcesoBatchPedidos(CasoUsoFake()).ejecutar_archivo(archivo)

    assert resultado.procesados == ["N-1", "N-2"]
    assert resultado.fallidos == [("linea-2", "JSON mal formado")]


# --- Mapeo y dependencias ----------------------------------------------------

def test_mapeo_valida_forma_pero_deja_reglas_de_negocio_al_nucleo():
    # Lista vacía tiene forma válida: rechazarla es una regla del caso de uso.
    assert solicitud_desde_dict(pedido_externo(items=[])).items == ()


MODULOS_PROHIBIDOS_EN_ENTRADAS = {
    "servicio_pedidos", "inventario", "inventario_stockcloud", "stockcloud_api",
    "pagos", "repositorio", "notificaciones", "precios", "envios", "facturacion",
}


@pytest.mark.parametrize("archivo", sorted(CARPETA_ENTRADA.glob("*.py")), ids=lambda p: p.name)
def test_adapters_de_entrada_no_dependen_de_infraestructura_ni_de_reglas(archivo):
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module.split(".")[-1])
        elif isinstance(nodo, ast.Import):
            importados.update(alias.name.split(".")[-1] for alias in nodo.names)
    assert importados.isdisjoint(MODULOS_PROHIBIDOS_EN_ENTRADAS), importados
