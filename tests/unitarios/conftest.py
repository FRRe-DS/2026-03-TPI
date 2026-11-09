"""Importar servicios sin cargar modelos Redis ni configuración de infraestructura."""
import importlib
import sys
from types import ModuleType
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def cargar_aislado():
    def cargar(nombre):
        modelos = ModuleType('app.modelos.cache_models')
        modelos.UbicacionesCond = Mock(name='UbicacionesCond')
        modelos.RegistroIdempotencia = Mock(name='RegistroIdempotencia')
        config = ModuleType('app.db.cache_config')
        config.cache = Mock(name='cache')
        with patch.dict(sys.modules, {
            'app.modelos.cache_models': modelos,
            'app.db.cache_config': config,
        }):
            # Ejecutar en un namespace independiente evita contaminar otras suites.
            spec = importlib.util.find_spec(nombre)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
        return modulo
    return cargar
