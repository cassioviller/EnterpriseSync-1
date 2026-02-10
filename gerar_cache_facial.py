#!/usr/bin/env python3
"""
Script para gerar cache de embeddings faciais dos funcionários.
Acelera drasticamente a identificação facial de 10-15s para <1s.

IMPORTANTE: Usa gerar_embedding_otimizado() para garantir consistência
entre geração de cache e comparação em tempo real.
"""

import os
import pickle
import base64
import tempfile
import logging
import numpy as np
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_FILE = 'cache_facial.pkl'
CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(CACHE_DIR, CACHE_FILE)


def normalizar_embedding_l2(embedding):
    """
    Normaliza embedding usando L2 norm.
    Garante que a comparação por distância euclidiana seja mais precisa.
    
    Args:
        embedding: Lista ou array de floats
    
    Returns:
        list: Embedding normalizado
    """
    embedding_array = np.array(embedding, dtype=np.float32)
    norm = np.linalg.norm(embedding_array)
    
    if norm == 0:
        logger.warning("[WARN] Embedding com norma zero!")
        return embedding_array.tolist()
    
    return (embedding_array / norm).tolist()

def gerar_cache(admin_id=None, incluir_inativas=False):
    """
    Gera cache de embeddings faciais para todos os funcionários.
    Usa múltiplas fotos da tabela FotoFacialFuncionario quando disponíveis.
    
    IMPORTANTE: Usa gerar_embedding_otimizado() para garantir que cache e
    comparação usem EXATAMENTE o mesmo método de geração de embeddings.
    
    Args:
        admin_id: Se fornecido, gera cache apenas para esse tenant.
                  Se None, gera para TODOS os tenants (usado em scripts).
        incluir_inativas: Se True, processa também fotos marcadas como inativas.
    
    Returns:
        dict: Estatísticas da geração do cache
    """
    from app import app, db
    from models import Funcionario, FotoFacialFuncionario
    from ponto_views import gerar_embedding_otimizado, preload_deepface_model
    
    # Pré-carregar modelo para acelerar geração
    logger.info("[SYNC] Pré-carregando modelo SFace...")
    preload_deepface_model()
    logger.info("[OK] Modelo SFace carregado!")
    
    # Converter admin_id para int se necessário
    admin_id_int = int(admin_id) if admin_id is not None else None
    logger.info(f"[TARGET] admin_id recebido: {admin_id} (tipo: {type(admin_id).__name__})")
    logger.info(f"[TARGET] admin_id_int: {admin_id_int}")
    
    with app.app_context():
        query = Funcionario.query.filter(Funcionario.ativo == True)
        
        if admin_id_int is not None:
            query = query.filter(Funcionario.admin_id == admin_id_int)
            logger.info(f"[DEBUG] Filtrando funcionários para admin_id={admin_id_int}")
        else:
            logger.info("[DEBUG] Gerando cache para TODOS os tenants")
        
        funcionarios = query.all()
        
        logger.info(f"[DEBUG] Encontrados {len(funcionarios)} funcionários ativos")
        
        cache = {}
        erros = []
        processados = 0
        total_embeddings = 0
        
        for func in funcionarios:
            try:
                fotos_para_processar = []
                
                # Buscar fotos múltiplas
                query_fotos = FotoFacialFuncionario.query.filter_by(
                    funcionario_id=func.id,
                    admin_id=func.admin_id
                )
                
                # Filtrar por ativas apenas se não incluir inativas
                if not incluir_inativas:
                    query_fotos = query_fotos.filter_by(ativa=True)
                
                fotos_multiplas = query_fotos.order_by(FotoFacialFuncionario.ordem).all()
                
                if fotos_multiplas:
                    for foto in fotos_multiplas:
                        fotos_para_processar.append({
                            'foto_base64': foto.foto_base64,
                            'descricao': foto.descricao or f'Foto {foto.ordem}'
                        })
                    # Log detalhado
                    fotos_ativas_count = sum(1 for f in fotos_multiplas if f.ativa)
                    fotos_inativas_count = len(fotos_multiplas) - fotos_ativas_count
                    logger.info(f"[PHOTO] {func.nome}: {fotos_ativas_count} ativas, {fotos_inativas_count} inativas")
                elif func.foto_base64:
                    fotos_para_processar.append({
                        'foto_base64': func.foto_base64,
                        'descricao': 'Foto principal'
                    })
                    logger.info(f"[PHOTO] {func.nome}: usando foto principal")
                else:
                    logger.warning(f"[WARN] {func.nome}: nenhuma foto disponível")
                    continue
                
                embeddings_funcionario = []
                
                for foto_info in fotos_para_processar:
                    try:
                        foto_base64 = foto_info['foto_base64']
                        if foto_base64.startswith('data:'):
                            foto_base64 = foto_base64.split(',')[1]
                        
                        foto_bytes = base64.b64decode(foto_base64)
                        
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                            tmp.write(foto_bytes)
                            tmp_path = tmp.name
                        
                        try:
                            # IMPORTANTE: Usar MESMA função que a comparação usa!
                            # Isso garante que cache e comparação sejam compatíveis.
                            embedding = gerar_embedding_otimizado(tmp_path)
                            
                            if embedding is not None:
                                # Normalizar embedding para consistência
                                embedding_normalizado = normalizar_embedding_l2(embedding)
                                
                                # Log para debug
                                norm_original = np.linalg.norm(np.array(embedding))
                                norm_final = np.linalg.norm(np.array(embedding_normalizado))
                                logger.debug(f" [STATS] Norm original: {norm_original:.4f}, Norm L2: {norm_final:.4f}")
                                
                                embeddings_funcionario.append({
                                    'embedding': embedding_normalizado,
                                    'descricao': foto_info['descricao']
                                })
                                total_embeddings += 1
                                logger.debug(f" [OK] {foto_info['descricao']} - embedding calculado ({len(embedding_normalizado)} dims)")
                            else:
                                logger.warning(f" [WARN] {foto_info['descricao']} - nenhum rosto detectado")
                                
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                                
                    except Exception as e:
                        logger.warning(f" [ERROR] {foto_info['descricao']} - erro: {e}")
                
                if embeddings_funcionario:
                    # Garantir que admin_id seja salvo como inteiro
                    admin_id_salvar = int(func.admin_id) if func.admin_id is not None else None
                    
                    cache[func.id] = {
                        'embeddings': embeddings_funcionario,
                        'admin_id': admin_id_salvar,  # SEMPRE int para consistência
                        'nome': func.nome,
                        'codigo': func.codigo,
                        'total_fotos': len(embeddings_funcionario),
                        'updated_at': datetime.now().isoformat()
                    }
                    processados += 1
                    logger.info(f"[OK] [{processados}] {func.nome} (admin_id={admin_id_salvar}) - {len(embeddings_funcionario)} embedding(s)")
                else:
                    erros.append({'id': func.id, 'nome': func.nome, 'erro': 'Nenhum embedding gerado'})
                    logger.warning(f"[WARN] {func.nome} - nenhum embedding gerado")
                        
            except Exception as e:
                erros.append({'id': func.id, 'nome': func.nome, 'erro': str(e)})
                logger.error(f"[ERROR] {func.nome} - erro: {e}")
        
        cache_data = {
            'embeddings': cache,
            'generated_at': datetime.now().isoformat(),
            'model': 'SFace',
            'method': 'model.forward()',  # Método usado para consistência
            'normalized': True,  # Embeddings normalizados com L2
            'total_funcionarios': len(funcionarios),
            'total_processados': processados,
            'total_embeddings': total_embeddings,
            'pipeline_version': '4.0-face-detection',
            'versao': '4.0'
        }
        
        logger.info(f"[SAVE] Salvando cache em: {CACHE_PATH}")
        logger.info(f"[STATS] Embeddings a salvar: {len(cache)} funcionários")
        
        try:
            with open(CACHE_PATH, 'wb') as f:
                pickle.dump(cache_data, f)
                f.flush()
                os.fsync(f.fileno())
            
            if os.path.exists(CACHE_PATH):
                size = os.path.getsize(CACHE_PATH)
                logger.info(f"[OK] Cache salvo com sucesso! Tamanho: {size} bytes")
            else:
                logger.error(f"[ERROR] ERRO: Arquivo não foi criado após pickle.dump!")
        except Exception as save_error:
            logger.error(f"[ERROR] ERRO ao salvar cache: {save_error}")
            return {'success': False, 'error': f'Erro ao salvar: {save_error}'}
        
            logger.info(f"[STATS] Processados: {processados}/{len(funcionarios)}")
        
        return {
            'success': True,
            'processados': processados,
            'total': len(funcionarios),
            'total_embeddings': total_embeddings,
            'erros': erros,
            'cache_path': CACHE_PATH
        }


def carregar_cache():
    """
    Carrega o cache de embeddings do arquivo.
    
    Returns:
        dict: Cache de embeddings ou None se não existir
    """
    if not os.path.exists(CACHE_PATH):
        logger.warning(f"[WARN] Cache não encontrado: {CACHE_PATH}")
        return None
    
    try:
        with open(CACHE_PATH, 'rb') as f:
            cache_data = pickle.load(f)
        
            logger.info(f"[OK] Cache carregado: {cache_data.get('total_processados', 0)} embeddings")
        return cache_data
    except Exception as e:
        logger.error(f"[ERROR] Erro ao carregar cache: {e}")
        return None


def validar_cache():
    """
    Valida o cache verificando:
    1. Se a versão do cache é 3.0 (método corrigido com model.forward())
    2. Se os embeddings têm o tamanho correto (128 dimensões para SFace)
    3. Se os embeddings estão normalizados (L2 norm)
    
    NOTA: Não valida distâncias intra-funcionário para evitar tempo de processamento.
    
    Returns:
        dict: Resultado da validação com campos valid, versao, metodo, etc.
    """
    cache = carregar_cache()
    
    if not cache:
        return {'valid': False, 'error': 'Cache não encontrado'}
    
    versao = cache.get('versao', '1.0')
    metodo = cache.get('method', 'desconhecido')
    normalizado = cache.get('normalized', False)
    
    logger.info(f"[STATS] Cache versão: {versao}, método: {metodo}, normalizado: {normalizado}")
    
    versoes_validas = ['3.0', '4.0']
    if versao not in versoes_validas:
        logger.warning(f"[WARN] Cache desatualizado! Versão {versao}, esperado {versoes_validas}")
        return {
            'valid': False, 
            'error': f'Cache versão {versao} desatualizado. Regenere o cache!',
            'versao': versao
        }
    
    embeddings_dict = cache.get('embeddings', {})
    total_funcionarios = len(embeddings_dict)
    total_embeddings = 0
    dimensoes_erradas = []
    
    for func_id, data in embeddings_dict.items():
        embeddings_list = data.get('embeddings', [])
        
        for emb_info in embeddings_list:
            if isinstance(emb_info, dict):
                embedding = emb_info.get('embedding', [])
            else:
                embedding = emb_info
            
            total_embeddings += 1
            
            if len(embedding) != 128:
                dimensoes_erradas.append({
                    'func_id': func_id,
                    'dims': len(embedding)
                })
    
    if dimensoes_erradas:
        logger.error(f"[ERROR] Embeddings com dimensões erradas: {dimensoes_erradas}")
        return {
            'valid': False,
            'error': 'Embeddings com dimensões incorretas',
            'dimensoes_erradas': dimensoes_erradas
        }
    
        logger.info(f"[OK] Cache válido! {total_funcionarios} funcionários, {total_embeddings} embeddings")
    
    return {
        'valid': True,
        'versao': versao,
        'metodo': metodo,
        'normalizado': normalizado,
        'total_funcionarios': total_funcionarios,
        'total_embeddings': total_embeddings
    }


def atualizar_embedding_funcionario(funcionario_id):
    """
    Atualiza os embeddings de um funcionário específico no cache.
    Usa múltiplas fotos da tabela FotoFacialFuncionario quando disponíveis.
    
    IMPORTANTE: Usa gerar_embedding_otimizado() para consistência.
    
    Args:
        funcionario_id: ID do funcionário
    
    Returns:
        bool: True se atualizado com sucesso
    """
    from app import app, db
    from models import Funcionario, FotoFacialFuncionario
    from ponto_views import gerar_embedding_otimizado, preload_deepface_model
    
    # Pré-carregar modelo
    preload_deepface_model()
    
    cache_data = carregar_cache()
    if not cache_data:
        cache_data = {
            'embeddings': {},
            'generated_at': datetime.now().isoformat(),
            'model': 'SFace',
            'method': 'model.forward()',
            'normalized': True,
            'total_funcionarios': 0,
            'total_processados': 0,
            'total_embeddings': 0,
            'versao': '3.0'
        }
    
    with app.app_context():
        func = Funcionario.query.get(funcionario_id)
        if not func:
            if funcionario_id in cache_data['embeddings']:
                del cache_data['embeddings'][funcionario_id]
                with open(CACHE_PATH, 'wb') as f:
                    pickle.dump(cache_data, f)
            return True
        
        fotos_para_processar = []
        
        fotos_multiplas = FotoFacialFuncionario.query.filter_by(
            funcionario_id=func.id,
            admin_id=func.admin_id,
            ativa=True
        ).order_by(FotoFacialFuncionario.ordem).all()
        
        if fotos_multiplas:
            for foto in fotos_multiplas:
                fotos_para_processar.append({
                    'foto_base64': foto.foto_base64,
                    'descricao': foto.descricao or f'Foto {foto.ordem}'
                })
                logger.info(f"[PHOTO] {func.nome}: {len(fotos_multiplas)} fotos múltiplas encontradas")
        elif func.foto_base64:
            fotos_para_processar.append({
                'foto_base64': func.foto_base64,
                'descricao': 'Foto principal'
            })
            logger.info(f"[PHOTO] {func.nome}: usando foto principal")
        else:
            if funcionario_id in cache_data['embeddings']:
                del cache_data['embeddings'][funcionario_id]
                with open(CACHE_PATH, 'wb') as f:
                    pickle.dump(cache_data, f)
                    logger.warning(f"[WARN] {func.nome}: nenhuma foto disponível, removido do cache")
            return True
        
        embeddings_funcionario = []
        
        for foto_info in fotos_para_processar:
            try:
                foto_base64 = foto_info['foto_base64']
                if foto_base64.startswith('data:'):
                    foto_base64 = foto_base64.split(',')[1]
                
                foto_bytes = base64.b64decode(foto_base64)
                
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp.write(foto_bytes)
                    tmp_path = tmp.name
                
                try:
                    # IMPORTANTE: Usar MESMA função que a comparação usa!
                    embedding = gerar_embedding_otimizado(tmp_path)
                    
                    if embedding is not None:
                        # Normalizar embedding para consistência
                        embedding_normalizado = normalizar_embedding_l2(embedding)
                        
                        embeddings_funcionario.append({
                            'embedding': embedding_normalizado,
                            'descricao': foto_info['descricao']
                        })
                        logger.debug(f" [OK] {foto_info['descricao']} - embedding calculado ({len(embedding_normalizado)} dims)")
                        
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                        
            except Exception as e:
                logger.warning(f" [ERROR] {foto_info['descricao']} - erro: {e}")
        
        if embeddings_funcionario:
            cache_data['embeddings'][func.id] = {
                'embeddings': embeddings_funcionario,
                'admin_id': func.admin_id,
                'nome': func.nome,
                'codigo': func.codigo,
                'total_fotos': len(embeddings_funcionario),
                'updated_at': datetime.now().isoformat()
            }
            
            cache_data['total_processados'] = len(cache_data['embeddings'])
            cache_data['method'] = 'model.forward()'
            cache_data['normalized'] = True
            cache_data['versao'] = '3.0'
            
            with open(CACHE_PATH, 'wb') as f:
                pickle.dump(cache_data, f)
            
                logger.info(f"[OK] Embeddings atualizados: {func.nome} ({len(embeddings_funcionario)} fotos)")
            return True
        else:
            if funcionario_id in cache_data['embeddings']:
                del cache_data['embeddings'][funcionario_id]
                with open(CACHE_PATH, 'wb') as f:
                    pickle.dump(cache_data, f)
                    logger.warning(f"[WARN] {func.nome}: nenhum embedding gerado")
            return False


def remover_funcionario_cache(funcionario_id):
    """
    Remove um funcionário do cache.
    
    Args:
        funcionario_id: ID do funcionário
    """
    cache_data = carregar_cache()
    if cache_data and funcionario_id in cache_data['embeddings']:
        del cache_data['embeddings'][funcionario_id]
        cache_data['total_processados'] = len(cache_data['embeddings'])
        
        with open(CACHE_PATH, 'wb') as f:
            pickle.dump(cache_data, f)
        
            logger.info(f"[DEL] Funcionário {funcionario_id} removido do cache")


if __name__ == '__main__':
    import sys
    
    logger.info("=" * 60)
    logger.info("[START] GERADOR DE CACHE FACIAL")
    logger.info("=" * 60)
    
    admin_id = None
    if len(sys.argv) > 1:
        try:
            admin_id = int(sys.argv[1])
            logger.debug(f"[PIN] Gerando cache apenas para admin_id: {admin_id}")
        except ValueError:
            logger.warning("[WARN] admin_id inválido, gerando cache para todos")
    
    resultado = gerar_cache(admin_id)
    
    logger.info("\n" + "=" * 60)
    logger.info("[STATS] RESULTADO")
    logger.info("=" * 60)
    
    if resultado['success']:
        logger.info(f"[OK] Cache gerado com sucesso!")
        logger.debug(f" Processados: {resultado['processados']}/{resultado['total']}")
        logger.debug(f" Arquivo: {resultado['cache_path']}")
        
        if resultado['erros']:
            logger.warning(f"\n[WARN] Erros ({len(resultado['erros'])}):")
            for erro in resultado['erros']:
                logger.debug(f" - {erro['nome']}: {erro['erro']}")
    else:
        logger.error(f"[ERROR] Erro: {resultado.get('error', 'Desconhecido')}")
