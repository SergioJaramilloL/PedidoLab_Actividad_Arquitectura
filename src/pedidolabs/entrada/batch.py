"""Adapter de entrada para el proceso batch nocturno.

Recorre un lote de pedidos (lista de dicts o archivo JSONL), traduce cada uno al
comando e invoca el MISMO puerto de entrada que usa REST.

Política propia de este canal: un pedido fallido no detiene el lote; se registra
y se continúa. Esa política vive aquí, no en el núcleo.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Tuple

from ..puertos import ProcesarPedido
from .mapeo import solicitud_desde_dict


@dataclass
class ResultadoLote:
    procesados: List[str] = field(default_factory=list)
    fallidos: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.procesados) + len(self.fallidos)


class ProcesoBatchPedidos:

    def __init__(self, caso_uso: ProcesarPedido):
        self.caso_uso = caso_uso

    def ejecutar(self, registros: Iterable[dict]) -> ResultadoLote:
        resultado = ResultadoLote()
        for numero, registro in enumerate(registros, start=1):
            self._procesar_registro(registro, numero, resultado)
        return resultado

    def ejecutar_archivo(self, ruta) -> ResultadoLote:
        """Lee un archivo JSONL (un pedido por línea) y procesa cada registro."""
        resultado = ResultadoLote()
        with Path(ruta).open("r", encoding="utf-8") as archivo:
            numero = 0
            for linea in archivo:
                linea = linea.strip()
                if not linea:
                    continue
                numero += 1
                try:
                    registro = json.loads(linea)
                except json.JSONDecodeError:
                    resultado.fallidos.append((f"linea-{numero}", "JSON mal formado"))
                    continue
                self._procesar_registro(registro, numero, resultado)
        return resultado

    def _procesar_registro(self, registro, numero, resultado: ResultadoLote) -> None:
        identificador = (
            str(registro.get("pedido_id", f"registro-{numero}"))
            if isinstance(registro, dict) else f"registro-{numero}"
        )
        try:
            pedido = self.caso_uso.procesar(solicitud_desde_dict(registro))
        except (ValueError, RuntimeError) as error:
            resultado.fallidos.append((identificador, str(error)))
        else:
            resultado.procesados.append(pedido.id)
