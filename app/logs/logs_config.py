"""
En este codigo se presentan la configuracion del logger que registra en el servidor las trazabilidades para 
auditorias, posee jerarquia para auditar o ver flujos.

DEBUG = 10 (máximo detalle interno, para depurar)

INFO = 20 (eventos normales de flujo/hitos)

WARNING = 30 (advertencias o situaciones anómalas no fatales)

ERROR = 40 (errores que impiden completar una operación)

CRITICAL = 50 (fallos graves del sistema)

al colocar uno de ellos, los mensajes de logger solo imprimen si es igual o mayor a su peso

el nivel se modifica en .env
"""

import logging, os
from pathlib import Path
from logging.handlers import RotatingFileHandler


def configurar_logging() -> None:
    nivel_str = os.getenv("LOG_LEVEL", "INFO").strip().upper()#aqui se modificaria el peso, se lo hace desde .env
    nivel = getattr(logging, nivel_str, logging.INFO)

    # Formato alineado con tu estándar: el mensaje ya lleva [trace_id=%s]|...
    formato = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    directorio_logs = Path(__file__).resolve().parent
    archivo_log = directorio_logs / "m4.log"
    root_logger = logging.getLogger()
    root_logger.setLevel(nivel)
    # Evita duplicar handlers si el módulo se importa o recarga más de una vez
    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setLevel(nivel)
            handler.setFormatter(formato)
    else:
        #OPCIONAL: lo siguiente es para que los registros de logs, se impriman por consola
        """
            console_handler = logging.StreamHandler()
            console_handler.setLevel(nivel)
            console_handler.setFormatter(formato)
            root_logger.addHandler(console_handler)

        """

        # si necesitás archivo en disco dentro del contenedor,
        # rotamos al llegar a 10 MB y conservamos máximo 3 archivos (30 MB tope aprox.)
        file_handler = RotatingFileHandler(
        filename=archivo_log,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",)
            
        file_handler.setLevel(nivel)
        file_handler.setFormatter(formato)
        root_logger.addHandler(file_handler)

    # Silenciar librerías ruidosas para que no saturen logs cuando LOG_LEVEL=DEBUG
    for libreria in ("urllib3", "sqlalchemy.engine", "httpcore", "httpx"):
        logging.getLogger(libreria).setLevel(logging.WARNING)