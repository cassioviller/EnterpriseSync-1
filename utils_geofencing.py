"""
Utilitários para Geofencing - Validação de localização GPS
Usado para garantir que funcionários estejam na obra ao registrar ponto
"""
from math import radians, sin, cos, sqrt, atan2
import logging

logger = logging.getLogger(__name__)

def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    """
    Calcula a distância em metros entre duas coordenadas GPS.
    Usa a fórmula de Haversine (precisão para distâncias curtas).
    
    Args:
        lat1, lon1: Coordenadas do ponto 1 (funcionário)
        lat2, lon2: Coordenadas do ponto 2 (obra)
    
    Returns:
        float: Distância em metros
    """
    R = 6371000  # Raio da Terra em metros
    
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distancia = R * c
    return distancia


def validar_localizacao_na_obra(lat_funcionario, lon_funcionario, obra):
    """
    Valida se o funcionário está dentro do raio permitido da obra.
    
    Args:
        lat_funcionario: Latitude do funcionário
        lon_funcionario: Longitude do funcionário
        obra: Objeto Obra com latitude, longitude e raio_geofence_metros
    
    Returns:
        tuple: (bool_valido, distancia_metros, mensagem)
            - bool_valido: True se dentro do raio
            - distancia_metros: Distância calculada (None se obra sem coordenadas)
            - mensagem: Mensagem descritiva do resultado
    """
    if not obra:
        return (True, None, "Sem obra vinculada")
    
    if not obra.latitude or not obra.longitude:
        logger.info(f"Obra {obra.nome} sem geofencing configurado")
        return (True, None, "Obra sem geofencing configurado")
    
    if lat_funcionario is None or lon_funcionario is None:
        logger.warning("Localização do funcionário não disponível")
        return (False, None, "Localização não disponível - ative o GPS")
    
    raio = obra.raio_geofence_metros or 100
    
    distancia = calcular_distancia_metros(
        lat_funcionario, lon_funcionario,
        obra.latitude, obra.longitude
    )
    
    logger.info(f"Geofencing: Funcionário a {distancia:.1f}m da obra {obra.nome} (raio: {raio}m)")
    
    if distancia <= raio:
        return (True, distancia, f"Dentro do raio ({distancia:.0f}m de {raio}m permitidos)")
    else:
        return (False, distancia, f"Fora do raio permitido ({distancia:.0f}m de {raio}m)")
