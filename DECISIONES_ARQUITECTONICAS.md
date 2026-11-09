# Decisiones arquitectónicas · Actividad final

**Arquitectura I · Especialización en Desarrollo de Software**
**Autor:** Sergio Andrés Jaramillo Luna

Documentos relacionados: [AS-IS](docs/01_AS-IS.md) · [Diagnóstico](docs/02_DIAGNOSTICO.md) · [TO-BE](docs/03_TO-BE.md)

---

## Resumen de la solución

| Presión | Elemento nuevo | Tipo |
|---|---|---|
| Dos canales de entrada | `ProcesarPedido` (en `puertos.py`) | Puerto de entrada |
| | `SolicitudPedido`, `LineaSolicitud` (`solicitudes.py`) | Comando / DTO |
| | `solicitud_desde_dict` (`entrada/mapeo.py`) | Mapeador compartido |
| | `ControladorPedidosREST` (`entrada/rest.py`) | Adapter de entrada |
| | `ProcesoBatchPedidos` (`entrada/batch.py`) | Adapter de entrada |
| Inventario remoto | `InventarioPedidos` (en `puertos.py`) | Puerto de salida |
| | `AdaptadorStockCloud` (`inventario_stockcloud.py`) | Adapter de salida |
| Selección por despliegue | `crear_inventario`, `crear_aplicacion` (`bootstrap.py`) | Composition Root |

### Justificación de las abstracciones de entrada

El enunciado pide justificar el puerto de entrada, el Command/DTO y la clase de mapeo, si se introducen. Se introdujeron los tres, cada uno por una razón concreta:

- **Puerto de entrada `ProcesarPedido`.** Sin él, REST y batch dependerían de la clase concreta `ServicioPedidos` y para probarlos habría que montar inventario, pagos, archivo y correo. Con el puerto, los adapters se prueban contra un fake (`CasoUsoFake` en `tests/test_entradas.py`). Es una sola operación: no se crearon `CancelarPedido` ni `ConsultarPedido` porque ningún requerimiento los pide.
- **Comando `SolicitudPedido`.** `procesar_pedido` recibe 13 parámetros posicionales, varios de ellos `str` consecutivos (`calle`, `ciudad`, `departamento`, `codigo_postal`). Que un adapter los pase en desorden no produce ningún error, solo datos corruptos. El comando hace el contrato explícito, con nombre en cada campo, y es inmutable (`frozen=True`). Además, desacopla la entrada de la clase de dominio `Producto`: los adapters construyen `LineaSolicitud` y el núcleo decide cómo convertirla.
- **Mapeador `solicitud_desde_dict`.** REST y batch reciben exactamente la misma forma de diccionario. Escribir la traducción en cada adapter la duplicaría. Una función (no una clase) es suficiente, porque no tiene estado ni variantes.

---

## F. Evaluación crítica

### 1. ¿Qué nueva dependencia hicieron explícita?

**La dependencia del núcleo con el inventario.** En el AS-IS, `ServicioPedidos` recibía `inventario` sin tipo ni contrato. Dependía, sin decirlo, de que el objeto tuviera `validar_disponibilidad` y `reservar` y de que lanzara `ValueError` ante falta de stock. Ahora esa dependencia es el puerto de salida `InventarioPedidos`, que documenta los dos métodos y el contrato de errores (`ValueError` para reglas de negocio, `RuntimeError` para fallas técnicas del proveedor).

También se hizo explícita **la dependencia de los canales de entrada con la aplicación**: antes no existía un contrato de entrada. Ahora es el puerto `ProcesarPedido` con el comando `SolicitudPedido`.

### 2. ¿Qué dependencia invirtieron o aislaron?

**Se aisló la dependencia con StockCloud.** Sin esta solución, procesar pedidos con StockCloud exigiría que `ServicioPedidos` llamara `query_stock` y `reserve_units` y leyera sus códigos (`ServicioPedidos → StockCloudAPI`). Con la solución, la dirección queda invertida: `ServicioPedidos → InventarioPedidos ← AdaptadorStockCloud → StockCloudAPI`. El detalle depende del contrato del núcleo, no al revés.

**En la entrada, los adapters dependen de una abstracción, no de una implementación:** `ControladorPedidosREST → ProcesarPedido ← ServicioPedidos`. Esto permite sustituir el caso de uso por un fake en las pruebas.

Las dos direcciones se verifican automáticamente con pruebas que analizan los `import` del código (ver la tabla de pruebas más abajo).

### 3. ¿Qué detalle externo quedó fuera del núcleo?

- **La API de StockCloud completa:** sus métodos (`query_stock`, `reserve_units`), su vocabulario (`sku`, `units`, `available_units`) y sus códigos de respuesta (`OK`, `NOT_FOUND`, `INSUFFICIENT_STOCK`, `INVALID_UNITS`, `RESERVED`). Solo `inventario_stockcloud.py` los conoce.
- **La representación externa de los pedidos:** el diccionario con claves en texto y `items` como lista de diccionarios. Solo la conoce el paquete `entrada/`.
- **Los conceptos propios de cada canal:** los códigos HTTP (400, 422, 502, 201) viven solo en el controller REST, y la política de "registrar el fallo y continuar" vive solo en el batch.

### 4. ¿Qué cambio futuro quedó localizado?

| Cambio futuro | Dónde se haría | Qué no se toca |
|---|---|---|
| Cambiar de proveedor de inventario o un nuevo código de StockCloud | Un adapter nuevo, o `AdaptadorStockCloud`, más una línea en `crear_inventario` | `ServicioPedidos`, entradas |
| Montar la API REST real con Flask o FastAPI | Una función de ruta delgada que llame a `ControladorPedidosREST.post_pedidos` | Núcleo, mapeo, salidas |
| Un tercer canal (CLI, cola de mensajes) | Un adapter nuevo sobre `ProcesarPedido` que reutilice el mapeo | Núcleo, REST, batch |
| Un campo nuevo en el formato externo | `entrada/mapeo.py` (y el comando, si la aplicación lo necesita) | Adapters REST y batch |
| Cambiar la política de errores del lote | `entrada/batch.py` | Núcleo, REST |

### 5. ¿Qué complejidad adicional introdujo su solución?

Se debe reconocer honestamente:

- **Más archivos y más saltos de lectura.** Para seguir una petición REST hasta la lógica de negocio ahora se pasa por controller → mapeo → comando → puerto → `procesar()` → `procesar_pedido()`. Antes era una llamada directa.
- **Dos formas de invocar el mismo caso de uso.** `procesar(solicitud)` (nueva) y `procesar_pedido(...)` (existente) conviven. Se mantuvo la segunda para no romper las 40 pruebas iniciales ni reescribir PedidoLab, pero un lector nuevo puede preguntarse cuál usar. Lo ideal a futuro sería migrar los invocadores a `procesar` y dejar `procesar_pedido` como detalle interno.
- **Traducción en dos pasos.** El dict se convierte en `SolicitudPedido` y luego en `Producto`/tuplas. Es una conversión más que mantener sincronizada si cambian los campos.
- **Contrato de errores por convención.** El puerto `InventarioPedidos` exige que todas las implementaciones lancen `ValueError` con mensajes equivalentes. `Protocol` no puede verificarlo, así que lo garantiza una prueba parametrizada (`test_local_y_stockcloud_cumplen_el_mismo_contrato_observable`).
- **Riesgo abierto.** Con un inventario remoto, la ventana entre validar stock, cobrar y reservar puede producir una reserva fallida después del cobro. Se documentó en el diagnóstico, pero no se resolvió (ver más abajo).

### 6. ¿Qué abstracción decidieron no crear y por qué?

- **Un adapter para el `Inventario` local.** El `Inventario` existente ya cumple `InventarioPedidos` por tipado estructural (`Protocol`): tiene los dos métodos con la semántica correcta. Envolverlo en un `AdaptadorInventarioLocal` que solo reenvíe llamadas no traduce nada, y sería una abstracción "para parecer hexagonal" (restricción 8).
- **Métodos extra en `InventarioPedidos`** (`devolver`, `ajustar`, `disponible`). El caso de uso no los usa y StockCloud no los ofrece. Incluirlos obligaría a implementarlos en el adapter sin ningún consumidor.
- **Un puerto de "fábrica" o registro de inventarios.** La elección de proveedor se resuelve con un `if` en el Composition Root, que es el único lugar donde debe vivir. Un registro dinámico, o pasar un contenedor a las clases, sería un Service Locator encubierto (restricción 4).
- **Una abstracción de "request/response HTTP"** (clases `Request`, `Response`, router). El controller recibe un `dict` y devuelve `{"status", "body"}`. Simular HTTP con más detalle no responde a ninguna presión real: cuando llegue el framework, él aportará esos objetos.
- **La compensación cobro/reserva** (`liberar` en inventario, `reembolsar` en pagos). Responde a un riesgo real, pero cambia las reglas del caso de uso y añade capacidades que ningún requerimiento actual pide. Se documentó como siguiente iteración en lugar de implementarse de forma especulativa.

---

## E. Pruebas nuevas y qué decisión demuestran

Pruebas iniciales: **40 (todas en verde)**. Pruebas nuevas: **29**. Total: **69**.

| Requisito del enunciado | Prueba(s) | Archivo |
|---|---|---|
| Un adapter de entrada puede trabajar contra un fake del caso de uso | `test_rest_trabaja_contra_un_fake_del_caso_de_uso`, `test_rest_rechaza_forma_invalida_sin_invocar_el_caso_de_uso`, `test_rest_solo_traduce_errores_del_nucleo_a_codigos_http` | `tests/test_entradas.py` |
| El batch reutiliza la misma capacidad de aplicación | `test_batch_reutiliza_la_misma_capacidad_y_la_misma_traduccion_que_rest`, `test_composition_root_conecta_ambas_entradas_a_la_misma_instancia_del_caso_de_uso` | `tests/test_entradas.py`, `tests/test_nucleo_fronteras.py` |
| StockCloud queda detrás de un adapter | `test_adapter_traduce_metodos_del_puerto_a_la_api_de_stockcloud`, `test_codigos_de_consulta_…`, `test_codigos_de_reserva_…`, `test_codigo_desconocido_de_stockcloud_es_falla_tecnica_no_de_negocio` | `tests/test_inventario_stockcloud.py` |
| El núcleo procesa un pedido sin depender de la API de StockCloud | `test_nucleo_procesa_solicitud_solo_con_puertos_y_fakes`, `test_servicio_pedidos_no_importa_stockcloud_ni_infraestructura`, `test_mismo_caso_de_uso_procesa_pedidos_con_inventario_local_o_stockcloud` | `tests/test_nucleo_fronteras.py` |
| Adicionales | Sustituibilidad local ↔ StockCloud, entradas sin imports de infraestructura, reglas de negocio en el núcleo, política de fallos del batch, lectura JSONL, flujo completo REST + batch con StockCloud | varios |

Las dos pruebas que analizan imports (`test_servicio_pedidos_no_importa_…` y `test_adapters_de_entrada_no_dependen_de_…`) convierten las restricciones arquitectónicas en verificaciones automáticas. Se comprobó que fallan si se agrega `from .stockcloud_api import StockCloudAPI` al servicio o un import de `repositorio` al controller REST.

---

## Otras decisiones menores

- **`demo.py` reparado.** En el repositorio base fallaba con `NameError` (`crear_servicio_pedidos` no estaba importado). No era parte de los entregables, pero se corrigió en un commit aparte porque es la forma más directa de ver la aplicación funcionando. Ahora usa `crear_aplicacion` y muestra ambas entradas: `python demo.py` (local) o `python demo.py stockcloud`.
- **`crear_servicio_pedidos` conserva su firma**, para no romper las pruebas existentes. `crear_aplicacion` la reutiliza.
- **`AdaptadorStockCloud` exige la API por constructor**, a diferencia de `AdaptadorPayFast`, que crea una por defecto. Así crear el detalle externo es siempre decisión del Composition Root.

---

## Conclusiones

1. **La arquitectura se evaluó por cómo absorbe el cambio, no por cuántos patrones aplica.** Las dos presiones de esta actividad (nuevos canales de entrada y un nuevo proveedor) se resolvieron agregando piezas en los bordes del sistema. Las reglas de negocio de `ServicioPedidos` y del dominio no cambiaron: el cuerpo de `procesar_pedido` quedó idéntico. Esa es la evidencia de que las fronteras estaban en el lugar correcto.

2. **Ports & Adapters es simétrico.** La demo docente aplicó el patrón del lado de salida (persistencia, pagos, notificaciones). Esta actividad completó el lado de entrada: así como `AdaptadorPayFast` traduce del núcleo hacia un proveedor, `ControladorPedidosREST` traduce desde un canal hacia el núcleo. En ambos casos el núcleo define el contrato y el detalle se adapta.

3. **Las dependencias implícitas también son dependencias.** El inventario "funcionaba" sin puerto, pero esa dependencia oculta era justo el punto por donde StockCloud habría entrado al núcleo. Hacerla explícita costó un `Protocol` de dos métodos y protegió al servicio de un cambio de proveedor.

4. **Un adapter traduce comportamiento, no solo nombres de métodos.** El valor real de `AdaptadorStockCloud` no está en renombrar `query_stock` como `validar_disponibilidad`, sino en convertir códigos de respuesta en el mismo contrato de errores del inventario local. Sin esa traducción semántica, el núcleo seguiría "contaminado" aunque no importara la API.

5. **No crear una abstracción también es una decisión de diseño.** Se descartaron un adapter para el inventario local, métodos de inventario sin consumidor, un registro de proveedores y una capa HTTP simulada. Cada abstracción tiene un costo de lectura y mantenimiento (pregunta 5), y solo se justifica si responde a una presión de cambio concreta.

6. **La facilidad de prueba es la señal de que la frontera funciona.** Los adapters de entrada se probaron sin inventario, pago, archivo ni correo, y el núcleo sin StockCloud. Que las restricciones queden expresadas como pruebas ejecutables convierte una intención de diseño en una garantía verificable en cada cambio.

7. **Quedó al menos un riesgo sin resolver, y así se reporta.** La consistencia entre cobro y reserva con un inventario remoto requiere una decisión de negocio (compensación o reordenamiento). Identificarlo y documentarlo, sin implementar una solución especulativa, es coherente con la idea de que la arquitectura evoluciona ante presiones reales.
