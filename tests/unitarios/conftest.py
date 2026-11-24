"""Importar servicios sin cargar modelos Redis ni configuración de infraestructura."""
import importlib
import sys
from types import ModuleType
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def cargar_aislado():
    def cargar(nombre):
        class NotFoundError(Exception):
            pass

        class FakeCacheResTemp:
            get = Mock(name='CacheResTemp.get')
            constructor = Mock(name='CacheResTemp')
            instance = Mock(name='CacheResTemp.instance')

            def __new__(cls, **kwargs):
                cls.constructor(**kwargs)
                return cls.instance

        modelos = ModuleType('app.modelos.cache_models')
        modelos.UbicacionesCond = Mock(name='UbicacionesCond')
        modelos.CacheResTemp = FakeCacheResTemp
        modelos.CacheEstOp = Mock(name='CacheEstOp')
        modelos.RegistroIdempotencia = Mock(name='RegistroIdempotencia')
        config = ModuleType('app.db.cache_config')
        config.cache = Mock(name='cache')
        redis_om = ModuleType('redis_om')
        redis_om.NotFoundError = NotFoundError
        redis_om_model = ModuleType('redis_om.model')
        redis_om_model.NotFoundError = NotFoundError
        with patch.dict(sys.modules, {
            'app.modelos.cache_models': modelos,
            'app.db.cache_config': config,
            'redis_om': redis_om,
            'redis_om.model': redis_om_model,
        }):
            # Ejecutar en un namespace independiente evita contaminar otras suites.
            spec = importlib.util.find_spec(nombre)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
        return modulo
    return cargar
