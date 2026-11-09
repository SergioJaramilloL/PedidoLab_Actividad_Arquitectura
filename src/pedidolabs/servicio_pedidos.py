from .cliente import Cliente
from .pedido import Pedido
from .producto import Producto
from .precios import calcular_descuento, calcular_beneficio_fidelidad
from .envios import calcular_costo_envio
from .facturacion import generar_factura
from .puertos import (
    InventarioPedidos,
    RepositorioPedidos,
    ProcesadorPago,
    NotificadorPedidos,
)
from .solicitudes import SolicitudPedido


class ServicioPedidos:
    """Servicio de aplicación. Implementa el puerto de entrada ProcesarPedido."""

    def __init__(
        self,
        inventario: InventarioPedidos,
        repositorio: RepositorioPedidos,
        procesador_pago: ProcesadorPago,
        notificador: NotificadorPedidos,
    ):
        self.inventario = inventario
        self.repositorio = repositorio
        self.procesador_pago = procesador_pago
        self.notificador = notificador
        self.ultima_factura = None
        self.ultimos_puntos = 0

    def procesar(self, solicitud: SolicitudPedido):
        """Puerto de entrada ProcesarPedido: traduce el comando a la operación
        existente para no duplicar ni reescribir el caso de uso."""
        items = [
            (Producto(linea.codigo, linea.nombre, linea.precio, linea.peso),
             linea.cantidad)
            for linea in solicitud.items
        ]
        return self.procesar_pedido(
            solicitud.pedido_id, solicitud.documento, solicitud.nombre,
            solicitud.email, solicitud.telefono, solicitud.tipo_cliente,
            solicitud.calle, solicitud.ciudad, solicitud.departamento,
            solicitud.codigo_postal, items, solicitud.numero_tarjeta,
            enviar_confirmacion=solicitud.enviar_confirmacion,
        )

    def procesar_pedido(
        self, pedido_id, documento, nombre, email, telefono, tipo_cliente,
        calle, ciudad, departamento, codigo_postal, items, numero_tarjeta,
        enviar_confirmacion=True,
    ):
        cliente = Cliente(
            documento, nombre, email, telefono, tipo_cliente,
            calle, ciudad, departamento, codigo_postal,
        )
        pedido = Pedido(
            pedido_id, cliente, calle, ciudad, departamento, codigo_postal
        )
        if not items:
            raise ValueError("El pedido debe contener al menos un producto")

        for producto, cantidad in items:
            self.inventario.validar_disponibilidad(producto.codigo, cantidad)
            pedido.agregar_item(producto, cantidad)

        subtotal = 0.0
        for item in pedido.items:
            subtotal += item.producto.precio * item.cantidad

        descuento = calcular_descuento(cliente, subtotal)
        envio = calcular_costo_envio(pedido, modalidad="ESTANDAR")
        total = subtotal - descuento + envio

        transaccion_id = self.procesador_pago.cobrar(numero_tarjeta, total)

        for item in pedido.items:
            self.inventario.reservar(item.producto.codigo, item.cantidad)

        pedido.estado = "CONFIRMADO"
        pedido.transaccion_id = transaccion_id
        pedido.total_pagado = total

        self.repositorio.guardar(pedido)

        self.ultima_factura = generar_factura(pedido, subtotal, descuento, envio)
        self.ultimos_puntos = calcular_beneficio_fidelidad(cliente, total)

        self.notificador.pago_recibido(cliente, pedido.id, transaccion_id, total)
        if enviar_confirmacion:
            self.notificador.pedido_confirmado(cliente, pedido.id, total)
        return pedido

    def calcular_resumen(self, pedido):
        subtotal = pedido.subtotal()
        descuento = calcular_descuento(pedido.cliente, subtotal)
        envio = calcular_costo_envio(pedido)
        return {
            "subtotal": subtotal,
            "descuento": descuento,
            "envio": envio,
            "total": subtotal - descuento + envio,
        }
