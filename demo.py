"""Demo de PedidoLab: un caso de uso, dos entradas, inventario intercambiable.

Uso (desde la raíz del repositorio):
    python demo.py              # inventario local
    python demo.py stockcloud   # inventario remoto StockCloud
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pedidolabs.bootstrap import crear_aplicacion  # noqa: E402
from pedidolabs.notificaciones import MENSAJES_ENVIADOS, limpiar_bandeja  # noqa: E402


def pedido_externo(pedido_id, cantidad_teclados=2):
    return {
        "pedido_id": pedido_id, "documento": "123", "nombre": "Ana",
        "email": "ana@example.com", "telefono": "3000000000",
        "tipo_cliente": "PREMIUM", "calle": "Cra 23 #45-67",
        "ciudad": "Manizales", "departamento": "Caldas", "codigo_postal": "170001",
        "items": [
            {"codigo": "P001", "nombre": "Teclado", "precio": 120_000,
             "peso": 0.8, "cantidad": cantidad_teclados},
            {"codigo": "P002", "nombre": "Mouse", "precio": 80_000,
             "peso": 0.3, "cantidad": 1},
        ],
        "numero_tarjeta": "4111111111111111", "enviar_confirmacion": True,
    }


def main(proveedor="local"):
    limpiar_bandeja()
    ruta = Path("demo_pedidos.jsonl")
    if ruta.exists():
        ruta.unlink()

    app = crear_aplicacion(proveedor, {"P001": 10, "P002": 20}, ruta)
    print(f"Inventario: {proveedor} -> {type(app.servicio.inventario).__name__}\n")

    respuesta = app.rest.post_pedidos(pedido_externo("PED-001"))
    print("REST POST /pedidos ->", respuesta["status"], respuesta["body"])
    print(app.servicio.ultima_factura, "\n")

    lote = app.batch.ejecutar([
        pedido_externo("PED-002"),
        pedido_externo("PED-003", cantidad_teclados=99),  # excede el stock
        {"pedido_id": "PED-004"},                         # forma inválida
    ])
    print(f"Batch nocturno -> procesados={lote.procesados}")
    for pedido_id, error in lote.fallidos:
        print(f"  fallido {pedido_id}: {error}")

    print("\nMensajes enviados:", len(MENSAJES_ENVIADOS))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "local")
