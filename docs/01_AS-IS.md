# A. Diagrama AS-IS · Punto de partida

![Diagrama AS-IS](img/01_AS-IS.png)

> El bloque Mermaid de abajo es la fuente del diagrama; GitHub lo dibuja directamente. La imagen se generó con mermaid-cli (layout ELK).

Convención: `A --> B` significa **A depende de B** (lo importa, lo recibe o lo invoca).
Las flechas punteadas `-.->` indican que un adapter **implementa** un puerto (también es una dependencia: el adapter conoce el contrato del puerto).

```mermaid
flowchart TB
    T["tests / demo.py<br/>(únicos invocadores actuales)"]
    B["bootstrap.py · Composition Root<br/>crear_servicio_pedidos(inventario, ruta)"]

    subgraph NUCLEO["NÚCLEO · aplicación + dominio"]
        direction TB
        S["ServicioPedidos<br/>procesar_pedido(13 parámetros posicionales)"]
        D["Dominio: Cliente · Pedido · Producto<br/>precios · envios · facturacion"]
        PR["«puerto salida»<br/>RepositorioPedidos"]
        PP["«puerto salida»<br/>ProcesadorPago"]
        PN["«puerto salida»<br/>NotificadorPedidos"]
    end

    subgraph ADP["ADAPTERS DE SALIDA"]
        AR["RepositorioArchivo"]
        AP["AdaptadorPayFast"]
        AN["NotificadorEmail"]
    end

    subgraph EXT["DETALLES EXTERNOS"]
        F[("pedidos.jsonl")]
        PF["PayFastAPI"]
        M["MENSAJES_ENVIADOS"]
        I["Inventario local<br/>(clase concreta)"]
        SC["StockCloudAPI<br/>(sin conectar)"]
    end

    T --> B
    T --> S
    T --> I
    B --> S
    B --> AR
    B --> AP
    B --> PF
    B --> AN

    S --> D
    S --> PR
    S --> PP
    S --> PN
    S == "⚠ dependencia implícita, sin puerto" ==> I

    AR -. implementa .-> PR
    AP -. implementa .-> PP
    AN -. implementa .-> PN
    AR --> F
    AP --> PF
    AN --> M

    classDef nucleo fill:#e8f1ff,stroke:#2f5d9e,color:#10233f
    classDef puerto fill:#fff7d6,stroke:#b38b00,color:#3d3000
    classDef adapter fill:#eaf7ea,stroke:#3d8b3d,color:#163816
    classDef externo fill:#f3f3f3,stroke:#888,color:#333
    classDef riesgo fill:#ffe9e6,stroke:#c0392b,color:#5a140c
    class S,D nucleo
    class PR,PP,PN puerto
    class AR,AP,AN adapter
    class F,PF,M,T,B externo
    class I,SC riesgo
```

## Lectura del diagrama

**Lo que ya está bien resuelto.** Persistencia, pagos y notificaciones cruzan la frontera del núcleo mediante puertos de salida (`RepositorioPedidos`, `ProcesadorPago`, `NotificadorPedidos`). `ServicioPedidos` no conoce `PayFastAPI`, el archivo JSONL ni la bandeja de correo: esos detalles se conectan desde `bootstrap.py`, que actúa como Composition Root.

**Lo que queda expuesto ante los nuevos requerimientos** (marcado en rojo):

1. **Inventario sin puerto.** `ServicioPedidos` recibe `inventario` sin contrato explícito. En la práctica depende de la forma concreta de `Inventario`: los métodos `validar_disponibilidad` y `reservar`, y la convención de lanzar `ValueError` cuando no hay stock. Es una dependencia real pero implícita.
2. **`StockCloudAPI` no encaja.** Ofrece `query_stock` y `reserve_units` con respuestas en diccionarios y códigos propios (`OK`, `NOT_FOUND`, `INSUFFICIENT_STOCK`, `RESERVED`…). No puede reemplazar a `Inventario` sin que alguien traduzca.
3. **No hay entradas.** Hoy el único "cliente" del caso de uso son las pruebas y la demo, que llaman `procesar_pedido` con 13 argumentos posicionales y construyen objetos `Producto` a mano. No existe un puerto de entrada ni una representación de la solicitud.
4. **`demo.py` está roto**: usa `crear_servicio_pedidos` sin importarlo.
