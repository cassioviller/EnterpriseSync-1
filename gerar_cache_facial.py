#!/usr/bin/env python3
"""
Script para gerar cache de embeddings faciais dos funcionários.
Acelera drasticamente a identificação facial de 10-15s para <1s.
"""

import os
import pickle
import base64
import tempfile
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_FILE = 'cache_facial.pkl'
CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(CACHE_DIR, CACHE_FILE)

def gerar_cache(admin_id=None):
    """
    Gera cache de embeddings faciais para todos os funcionários.
    Usa múltiplas fotos da tabela FotoFacialFuncionario quando disponíveis.
    
    Args:
        admin_id: Se fornecido, gera cache apenas para esse tenant
    
    Returns:
        dict: Estatísticas da geração do cache
    """
    from app import app, db
    from models import Funcionario, FotoFacialFuncionario
    
    try:
        from deepface import DeepFace
    except ImportError:
        logger.error("DeepFace não está instalado")
        return {'success': False, 'error': 'DeepFace não instalado'}
    
    with app.app_context():
        query = Funcionario.query.filter(Funcionario.ativo == True)
        
        if admin_id:
            query = query.filter(Funcionario.admin_id == admin_id)
        
        funcionarios = query.all()
        
        logger.info(f"🔍 Encontrados {len(funcionarios)} funcionários ativos")
        
        cache = {}
        erros = []
        processados = 0
        total_embeddings = 0
        
        for func in funcionarios:
            try:
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
                    logger.info(f"📷 {func.nome}: {len(fotos_multiplas)} fotos múltiplas encontradas")
                elif func.foto_base64:
                    fotos_para_processar.append({
                        'foto_base64': func.foto_base64,
                        'descricao': 'Foto principal'
                    })
                    logger.info(f"📷 {func.nome}: usando foto principal")
                else:
                    logger.warning(f"⚠️ {func.nome}: nenhuma foto disponível")
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
                            embedding_result = DeepFace.represent(
                                img_path=tmp_path,
                                model_name='SFace',
                                enforce_detection=False,
                                detector_backend='opencv'
                            )
                            
                            if embedding_result and len(embedding_result) > 0:
                                embedding = embedding_result[0]['embedding']
                                embeddings_funcionario.append({
                                    'embedding': embedding,
                                    'descricao': foto_info['descricao']
                                })
                                total_embeddings += 1
                                logger.debug(f"  ✅ {foto_info['descricao']} - embedding calculado")
                            else:
                                logger.warning(f"  ⚠️ {foto_info['descricao']} - nenhum rosto detectado")
                                
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                                
                    except Exception as e:
                        logger.warning(f"  ❌ {foto_info['descricao']} - erro: {e}")
                
                if embeddings_funcionario:
                    cache[func.id] = {
                        'embeddings': embeddings_funcionario,
                        'admin_id': func.admin_id,
                        'nome': func.nome,
                        'codigo': func.codigo,
                        'total_fotos': len(embeddings_funcionario),
                        'updated_at': datetime.now().isoformat()
                    }
                    processados += 1
                    logger.info(f"✅ [{processados}] {func.nome} - {len(embeddings_funcionario)} embedding(s) calculado(s)")
                else:
                    erros.append({'id': func.id, 'nome': func.nome, 'erro': 'Nenhum embedding gerado'})
                    logger.warning(f"⚠️ {func.nome} - nenhum embedding gerado")
                        
            except Exception as e:
                erros.append({'id': func.id, 'nome': func.nome, 'erro': str(e)})
                logger.error(f"❌ {func.nome} - erro: {e}")
        
        cache_data = {
            'embeddings': cache,
            'generated_at': datetime.now().isoformat(),
            'model': 'SFace',
            'total_funcionarios': len(funcionarios),
            'total_processados': processados,
            'total_embeddings': total_embeddings,
            'versao': '2.0'
        }
        
        logger.info(f"💾 Salvando cache em: {CACHE_PATH}")
        logger.info(f"📊 Embeddings a salvar: {len(cache)} funcionários")
        
        try:
            with open(CACHE_PATH, 'wb') as f:
                pickle.dump(cache_data, f)
                f.flush()
                os.fsync(f.fileno())
            
            if os.path.exists(CACHE_PATH):
                size = os.path.getsize(CACHE_PATH)
                logger.info(f"✅ Cache salvo com sucesso! Tamanho: {size} bytes")
            else:
                logger.error(f"❌ ERRO: Arquivo não foi criado após pickle.dump!")
        except Exception as save_error:
            logger.error(f"❌ ERRO ao salvar cache: {save_error}")
            return {'success': False, 'error': f'Erro ao salvar: {save_error}'}
        
        logger.info(f"📊 Processados: {processados}/{len(funcionarios)}")
        
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
        logger.warning(f"⚠️ Cache não encontrado: {CACHE_PATH}")
        return None
    
    try:
        with open(CACHE_PATH, 'rb') as f:
            cache_data = pickle.load(f)
        
        logger.info(f"✅ Cache carregado: {cache_data.get('total_processados', 0)} embeddings")
        return cache_data
    except Exception as e:
        logger.error(f"❌ Erro ao carregar cache: {e}")
        return None


def atualizar_embedding_funcionario(funcionario_id):
    """
    Atualiza os embeddings de um funcionário específico no cache.
    Usa múltiplas fotos da tabela FotoFacialFuncionario quando disponíveis.
    
    Args:
        funcionario_id: ID do funcionário
    
    Returns:
        bool: True se atualizado com sucesso
    """
    from app import app, db
    from models import Funcionario, FotoFacialFuncionario
    
    try:
        from deepface import DeepFace
    except ImportError:
        logger.error("DeepFace não está instalado")
        return False
    
    cache_data = carregar_cache()
    if not cache_data:
        cache_data = {
            'embeddings': {},
            'generated_at': datetime.now().isoformat(),
            'model': 'SFace',
            'total_funcionarios': 0,
            'total_processados': 0,
            'total_embeddings': 0,
            'versao': '2.0'
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
            logger.info(f"📷 {func.nome}: {len(fotos_multiplas)} fotos múltiplas encontradas")
        elif func.foto_base64:
            fotos_para_processar.append({
                'foto_base64': func.foto_base64,
                'descricao': 'Foto principal'
            })
            logger.info(f"📷 {func.nome}: usando foto principal")
        else:
            if funcionario_id in cache_data['embeddings']:
                del cache_data['embeddings'][funcionario_id]
                with open(CACHE_PATH, 'wb') as f:
                    pickle.dump(cache_data, f)
            logger.warning(f"⚠️ {func.nome}: nenhuma foto disponível, removido do cache")
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
                    embedding_result = DeepFace.represent(
                        img_path=tmp_path,
                        model_name='SFace',
                        enforce_detection=False,
                        detector_backend='opencv'
                    )
                    
                    if embedding_result and len(embedding_result) > 0:
                        embedding = embedding_result[0]['embedding']
                        embeddings_funcionario.append({
                            'embedding': embedding,
                            'descricao': foto_info['descricao']
                        })
                        logger.debug(f"  ✅ {foto_info['descricao']} - embedding calculado")
                        
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                        
            except Exception as e:
                logger.warning(f"  ❌ {foto_info['descricao']} - erro: {e}")
        
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
            cache_data['versao'] = '2.0'
            
            with open(CACHE_PATH, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info(f"✅ Embeddings atualizados: {func.nome} ({len(embeddings_funcionario)} fotos)")
            return True
        else:
            if funcionario_id in cache_data['embeddings']:
                del cache_data['embeddings'][funcionario_id]
                with open(CACHE_PATH, 'wb') as f:
                    pickle.dump(cache_data, f)
            logger.warning(f"⚠️ {func.nome}: nenhum embedding gerado")
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
        
        logger.info(f"🗑️ Funcionário {funcionario_id} removido do cache")


if __name__ == '__main__':
    import sys
    
    print("=" * 60)
    print("🚀 GERADOR DE CACHE FACIAL")
    print("=" * 60)
    
    admin_id = None
    if len(sys.argv) > 1:
        try:
            admin_id = int(sys.argv[1])
            print(f"📌 Gerando cache apenas para admin_id: {admin_id}")
        except ValueError:
            print("⚠️ admin_id inválido, gerando cache para todos")
    
    resultado = gerar_cache(admin_id)
    
    print("\n" + "=" * 60)
    print("📊 RESULTADO")
    print("=" * 60)
    
    if resultado['success']:
        print(f"✅ Cache gerado com sucesso!")
        print(f"   Processados: {resultado['processados']}/{resultado['total']}")
        print(f"   Arquivo: {resultado['cache_path']}")
        
        if resultado['erros']:
            print(f"\n⚠️ Erros ({len(resultado['erros'])}):")
            for erro in resultado['erros']:
                print(f"   - {erro['nome']}: {erro['erro']}")
    else:
        print(f"❌ Erro: {resultado.get('error', 'Desconhecido')}")
