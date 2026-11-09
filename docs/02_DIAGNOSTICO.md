# B. Diagnóstico arquitectónico

Formato de cada hallazgo: **presión de cambio → dependencia afectada → decisión propuesta**.

El diagnóstico se hizo sobre el AS-IS ([01_AS-IS.md](01_AS-IS.md)), antes de escribir código.

---

## R1 · Dos canales de entrada podrían duplicar el caso de uso

**Presión de cambio.** La organización quiere recibir pedidos por una API REST futura y por un proceso batch nocturno.

**Dependencia afectada.** Hoy quien quiera procesar un pedido depende de la firma concreta `ServicioPedidos.procesar_pedido(...)`: 13 argumentos posicionales y una lista de tuplas `(Producto, cantidad)` que el invocador debe construir. Si cada entrada traduce el diccionario externo por su cuenta, la traducción queda duplicada. Peor aún, es tentador que el controller "ayude" calculando o validando reglas, y terminaríamos con un *Fat Controller* que solo mueve la lógica de sitio.

**Decisión propuesta.**
- Un **puerto de entrada `ProcesarPedido`** con una sola operación, `procesar(solicitud)`. Los adapters dependerán de esa capacidad y no de la clase concreta, lo que además permite probarlos con un fake.
- Un **comando `SolicitudPedido`** (DTO inmutable) como contrato de lo que la aplicación necesita recibir. Reemplaza los 13 parámetros posicionales, donde intercambiar `ciudad` y `departamento` no produce ningún error visible.
- Un **mapeador compartido** `solicitud_desde_dict` para la traducción *diccionario externo → comando*. REST y batch reciben la misma representación, así que la traducción se escribe una sola vez.
- `ServicioPedidos` implementará `procesar(solicitud)` delegando en el `procesar_pedido` existente. **No se reescribe** el caso de uso y las pruebas actuales siguen funcionando.

---

## R2 · El inventario es una dependencia real pero implícita

**Presión de cambio.** Algunos despliegues usarán el proveedor externo StockCloud en lugar del inventario local.

**Dependencia afectada.** `ServicioPedidos` recibe `inventario` sin tipo ni contrato. Funciona solo porque `Inventario` tiene `validar_disponibilidad` y `reservar`. Si se conectara `StockCloudAPI` directamente, el servicio tendría que llamar `query_stock` / `reserve_units` y leer `status`, lo que viola la restricción 3 y mete un detalle del proveedor dentro del núcleo.

**Decisión propuesta.**
- Un **puerto de salida `InventarioPedidos`** en `puertos.py` con **solo las dos capacidades que la aplicación usa**: validar disponibilidad y reservar. No se incluyen `devolver`, `ajustar` ni `disponible`, porque el caso de uso no los necesita y StockCloud no los ofrece.
- El `Inventario` local **ya cumple** ese contrato por tipado estructural (`Protocol`), así que no necesita adapter.
- Un **`AdaptadorStockCloud`** implementa el puerto y traduce hacia `StockCloudAPI`, siguiendo el mismo patrón que `AdaptadorPayFast`.

---

## R3 · Semántica de errores distinta entre proveedores

**Presión de cambio.** StockCloud no lanza excepciones: responde diccionarios con códigos propios (`NOT_FOUND`, `INSUFFICIENT_STOCK`, `INVALID_UNITS`, `RESERVED`).

**Dependencia afectada.** El caso de uso, y ahora también los adapters de entrada, asumen que un problema de stock se manifiesta como `ValueError`. Si los códigos de StockCloud se filtraran hacia el núcleo, cada punto que hoy captura `ValueError` tendría que aprender un segundo idioma de errores.

**Decisión propuesta.** El `AdaptadorStockCloud` traduce **todos** los códigos de negocio a `ValueError`, con los mismos mensajes que produce el inventario local. Así el núcleo y las entradas ven el mismo comportamiento con cualquier proveedor. Un código desconocido se traduce a `RuntimeError` (falla técnica del proveedor), igual que hace `cobrar_con_payfast` con códigos de PayFast no reconocidos.

---

## R4 · ¿Quién decide qué inventario se usa en cada despliegue?

**Presión de cambio.** "Algunos despliegues" usarán StockCloud y otros el inventario local.

**Dependencia afectada.** La elección de implementación. Si la decisión se toma dentro de `ServicioPedidos` (un `if proveedor == "stockcloud"`), el núcleo vuelve a conocer a StockCloud. Si se resuelve con un registro global o un *Service Locator*, la dependencia queda oculta, lo que prohíbe la restricción 4.

**Decisión propuesta.** La elección vive **en el Composition Root** (`bootstrap.py`), con una fábrica explícita `crear_inventario(proveedor, stock_inicial)` y una función `crear_aplicacion(...)` que ensambla el servicio y **ambas entradas sobre la misma instancia** del caso de uso. Todas las dependencias se pasan por constructor.

---

## R5 · Un pedido inválido no debería detener el lote nocturno

**Presión de cambio.** El batch procesa muchos pedidos sin un humano presente.

**Dependencia afectada.** La política ante fallos. El caso de uso lanza excepciones pedido por pedido, lo cual es correcto para REST, que responde un error al cliente. En un lote, una excepción no controlada abortaría los pedidos restantes.

**Decisión propuesta.** La política de *continuar y reportar* es responsabilidad del **adapter batch**, no del núcleo. El adapter captura los errores de negocio y técnicos de cada registro y devuelve un `ResultadoLote` con los procesados y los fallidos. El núcleo no cambia.

---

## Riesgo abierto (identificado, no resuelto en esta actividad)

**Consistencia entre cobro y reserva con un inventario remoto.** El caso de uso existente valida stock, cobra y **después** reserva. Con un inventario local en memoria la ventana entre validar y reservar es despreciable. Con StockCloud, otro cliente podría consumir el stock en ese intervalo y la reserva fallaría **después de cobrar**. Resolverlo exigiría una compensación (reembolso) o invertir el orden reserva → cobro → liberación, y eso cambia reglas del caso de uso y añade capacidades que hoy no existen (`liberar` en el puerto, `reembolsar` en pagos). Como la actividad pide no reescribir PedidoLab y que cada abstracción responda a una presión concreta, se documenta como riesgo para una iteración futura en lugar de implementarlo especulativamente.
