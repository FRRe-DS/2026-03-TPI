from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from ..errores.exceptionsSemanticos import NoAutenticado,SinPermiso

#URL del Realm de Keycloak
KEYCLOAK_CLAVE_PUBLICA = "http://keycloak-server:8080/realms/ds-2026-realm/protocol/openid-connect/certs"

# 2. PyJWKClient gestiona las claves públicas en la ram
token_publico = PyJWKClient(KEYCLOAK_CLAVE_PUBLICA)

seguridad_segun_contrato = HTTPBearer()

def validar_token_keycloak(credenciales: HTTPAuthorizationCredentials = Depends(seguridad_segun_contrato)) -> dict:
    token = credenciales.credentials
    try:
        # PyJWT busca la clave pública directamente en la cache si es que ya no lo esta
        clave = token_publico.get_signing_key_from_jwt(token)

        # decodifica, valida firma, algoritmo y expiración
        verificacion = jwt.decode(
            token,
            clave.key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Ajustar si necesitamos audience en Keycloak
        )
        return verificacion

    except jwt.ExpiredSignatureError:
        raise NoAutenticado(detail=f"Certificado de acceso expirado")#401
    except jwt.PyJWTError as e:
        raise NoAutenticado(detail=f"Certificado de acceso inválido o corrupto: {str(e)}")#401

def verificar_rol(rol_requerido: str):
    def dependencia_rol(verificacion: dict = Depends(validar_token_keycloak)):
        # Keycloak almacena los roles del realm dentro de la estructura 'realm_access' -> 'roles'
        roles_usuario = verificacion.get("realm_access", {}).get("roles", [])
        
        if rol_requerido not in roles_usuario:
            raise SinPermiso()#403
        return verificacion
    return dependencia_rol
