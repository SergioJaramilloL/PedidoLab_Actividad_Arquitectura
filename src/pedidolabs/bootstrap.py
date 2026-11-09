"""Composition Root de PedidoLab.

Este módulo conoce los detalles concretos y ensambla la aplicación.
La lógica de aplicación no necesita importarlos.

Aquí, y solo aquí, se decide:
- qué inventario usa cada despliegue (local o StockCloud),
- qué adapters de salida se conectan,
- qué adapters de entrada exponen el caso de uso.
Todas las dependencias se entregan por constructor (sin Service Locator ni globales).
"""

from dataclasses import dataclass

from .entrada.batch import ProcesoBatchPedidos
from .entrada.rest import ControladorPedidosREST
from .inventario import Inventario
from .inventario_stockcloud import AdaptadorStockCloud
from .notificaciones import NotificadorEmail
from .pagos import AdaptadorPayFast, PayFastAPI
from .repositorio import RepositorioArchivo
from .servicio_pedidos import ServicioPedidos
from .stockcloud_api import StockCloudAPI

PROVEEDORES_INVENTARIO = ("local", "stockcloud")


def crear_servicio_pedidos(inventario, ruta_pedidos="pedidos.jsonl"):
    repositorio = RepositorioArchivo(ruta_pedidos)
    procesador_pago = AdaptadorPayFast(PayFastAPI())
    notificador = NotificadorEmail()

    return ServicioPedidos(
        inventario=inventario,
        repositorio=repositorio,
        procesador_pago=procesador_pago,
        notificador=notificador,
    )


def crear_inventario(proveedor="local", stock_inicial=None):
    """Elige la implementación del puerto InventarioPedidos para el despliegue."""
    if proveedor == "local":
        return Inventario(stock_inicial)
    if proveedor == "stockcloud":
        return AdaptadorStockCloud(StockCloudAPI(stock_inicial))
    raise ValueError(
        f"Proveedor de inventario no soportado: {proveedor}. "
        f"Opciones: {', '.join(PROVEEDORES_INVENTARIO)}"
    )


@dataclass
class AplicacionPedidoLab:
    """Resultado del ensamblaje: un caso de uso y sus dos canales de entrada."""
    servicio: ServicioPedidos
    rest: ControladorPedidosREST
    batch: ProcesoBatchPedidos


def crear_aplicacion(proveedor_inventario="local", stock_inicial=None,
                     ruta_pedidos="pedidos.jsonl"):
    inventario = crear_inventario(proveedor_inventario, stock_inicial)
    servicio = crear_servicio_pedidos(inventario, ruta_pedidos)
    return AplicacionPedidoLab(
        servicio=servicio,
        # Ambas entradas reciben la MISMA instancia del caso de uso.
        rest=ControladorPedidosREST(servicio),
        batch=ProcesoBatchPedidos(servicio),
    )
