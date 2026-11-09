"""Traducción entre la representación externa de un pedido y el comando de la aplicación.

REST y batch reciben la misma forma de diccionario, por eso comparten este mapeador
en lugar de duplicar la traducción en cada adapter.

Aquí solo se valida FORMA (campos presentes, tipos convertibles).
Las reglas de NEGOCIO (pedido sin items, stock, pago...) las aplica el núcleo.
"""

from ..solicitudes import LineaSolicitud, SolicitudPedido


class SolicitudInvalida(ValueError):
    """La representación externa no tiene la forma esperada."""


CAMPOS_TEXTO = (
    "pedido_id", "documento", "nombre", "email", "telefono", "tipo_cliente",
    "calle", "ciudad", "departamento", "codigo_postal", "numero_tarjeta",
)
CAMPOS_ITEM = ("codigo", "nombre", "precio", "peso", "cantidad")


def solicitud_desde_dict(datos) -> SolicitudPedido:
    if not isinstance(datos, dict):
        raise SolicitudInvalida("La entrada debe ser un objeto (diccionario)")

    faltantes = [c for c in CAMPOS_TEXTO + ("items",) if c not in datos]
    if faltantes:
        raise SolicitudInvalida(f"Faltan campos obligatorios: {', '.join(faltantes)}")

    if not isinstance(datos["items"], list):
        raise SolicitudInvalida("'items' debe ser una lista")

    enviar_confirmacion = datos.get("enviar_confirmacion", True)
    if not isinstance(enviar_confirmacion, bool):
        raise SolicitudInvalida("'enviar_confirmacion' debe ser true o false")

    return SolicitudPedido(
        **{campo: str(datos[campo]) for campo in CAMPOS_TEXTO},
        items=tuple(
            _linea_desde_dict(item, posicion)
            for posicion, item in enumerate(datos["items"], start=1)
        ),
        enviar_confirmacion=enviar_confirmacion,
    )


def _linea_desde_dict(item, posicion) -> LineaSolicitud:
    if not isinstance(item, dict):
        raise SolicitudInvalida(f"Item {posicion}: debe ser un objeto (diccionario)")

    faltantes = [c for c in CAMPOS_ITEM if c not in item]
    if faltantes:
        raise SolicitudInvalida(
            f"Item {posicion}: faltan campos obligatorios: {', '.join(faltantes)}"
        )

    try:
        return LineaSolicitud(
            codigo=str(item["codigo"]),
            nombre=str(item["nombre"]),
            precio=float(item["precio"]),
            peso=float(item["peso"]),
            cantidad=int(item["cantidad"]),
        )
    except (TypeError, ValueError):
        raise SolicitudInvalida(
            f"Item {posicion}: 'precio' y 'peso' deben ser numéricos y 'cantidad' entera"
        ) from None
