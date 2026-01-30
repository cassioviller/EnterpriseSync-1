"""
Utilitários para validação de geolocalização (Geofencing)
Sistema de Cerca Virtual para controle de ponto
"""
from math import radians, sin, cos, sqrt, atan2
import logging

logger = logging.getLogger(__name__)

def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    """
    Calcula a distância em metros entre duas coordenadas GPS.
    Usa a fórmula de Haversine.
    
    Args:
        lat1, lon1: Coordenadas do ponto 1 (latitude, longitude)
        lat2, lon2: Coordenadas do ponto 2 (latitude, longitude)
    
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
    Valida se o funcionário está dentro do raio da obra.
    
    Args:
        lat_funcionario: Latitude do funcionário
        lon_funcionario: Longitude do funcionário
        obra: Objeto Obra com latitude, longitude e raio_geofence_metros
    
    Returns:
        tuple: (bool, float, str) - (válido, distância, mensagem)
    """
    if not obra:
        return (True, None, "Obra não informada")
    
    if not obra.latitude or not obra.longitude:
        logger.info(f"Obra {obra.nome} sem geofencing configurado")
        return (True, None, "Obra sem geofencing configurado")
    
    if lat_funcionario is None or lon_funcionario is None:
        logger.warning("Coordenadas do funcionário não fornecidas")
        return (True, None, "Localização não fornecida")
    
    raio = obra.raio_geofence_metros or 100
    
    distancia = calcular_distancia_metros(
        lat_funcionario, lon_funcionario,
        obra.latitude, obra.longitude
    )
    
    logger.info(f"Geofencing: Distância calculada = {distancia:.1f}m, Raio permitido = {raio}m")
    
    if distancia <= raio:
        return (True, distancia, f"Dentro do raio ({distancia:.0f}m de {raio}m)")
    else:
        return (False, distancia, f"Fora do raio ({distancia:.0f}m de {raio}m)")
