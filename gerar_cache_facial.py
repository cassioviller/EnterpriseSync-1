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
    Gera cache de embeddings faciais para todos os funcionários com foto.
    
    Args:
        admin_id: Se fornecido, gera cache apenas para esse tenant
    
    Returns:
        dict: Estatísticas da geração do cache
    """
    from app import app, db
    from models import Funcionario
    
    try:
        from deepface import DeepFace
    except ImportError:
        logger.error("DeepFace não está instalado")
        return {'success': False, 'error': 'DeepFace não instalado'}
    
    with app.app_context():
        query = Funcionario.query.filter(
            Funcionario.ativo == True,
            Funcionario.foto_base64 != None,
            Funcionario.foto_base64 != ''
        )
        
        if admin_id:
            query = query.filter(Funcionario.admin_id == admin_id)
        
        funcionarios = query.all()
        
        logger.info(f"🔍 Encontrados {len(funcionarios)} funcionários com foto")
        
        cache = {}
        erros = []
        processados = 0
        
        for func in funcionarios:
            try:
                foto_base64 = func.foto_base64
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
                        
                        cache[func.id] = {
                            'embedding': embedding,
                            'admin_id': func.admin_id,
                            'nome': func.nome,
                            'codigo': func.codigo,
                            'updated_at': datetime.now().isoformat()
                        }
                        processados += 1
                        logger.info(f"✅ [{processados}] {func.nome} - embedding calculado")
                    else:
                        erros.append({'id': func.id, 'nome': func.nome, 'erro': 'Nenhum rosto detectado'})
                        logger.warning(f"⚠️ {func.nome} - nenhum rosto detectado")
                        
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                        
            except Exception as e:
                erros.append({'id': func.id, 'nome': func.nome, 'erro': str(e)})
                logger.error(f"❌ {func.nome} - erro: {e}")
        
        cache_data = {
            'embeddings': cache,
            'generated_at': datetime.now().isoformat(),
            'model': 'SFace',
            'total_funcionarios': len(funcionarios),
            'total_processados': processados
        }
        
        with open(CACHE_PATH, 'wb') as f:
            pickle.dump(cache_data, f)
        
        logger.info(f"💾 Cache salvo em {CACHE_PATH}")
        logger.info(f"📊 Processados: {processados}/{len(funcionarios)}")
        
        return {
            'success': True,
            'processados': processados,
            'total': len(funcionarios),
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
    Atualiza o embedding de um funcionário específico no cache.
    Útil quando a foto de um funcionário é atualizada.
    
    Args:
        funcionario_id: ID do funcionário
    
    Returns:
        bool: True se atualizado com sucesso
    """
    from app import app, db
    from models import Funcionario
    
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
            'total_processados': 0
        }
    
    with app.app_context():
        func = Funcionario.query.get(funcionario_id)
        if not func or not func.foto_base64:
            if funcionario_id in cache_data['embeddings']:
                del cache_data['embeddings'][funcionario_id]
                with open(CACHE_PATH, 'wb') as f:
                    pickle.dump(cache_data, f)
            return True
        
        try:
            foto_base64 = func.foto_base64
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
                    
                    cache_data['embeddings'][func.id] = {
                        'embedding': embedding,
                        'admin_id': func.admin_id,
                        'nome': func.nome,
                        'codigo': func.codigo,
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    cache_data['total_processados'] = len(cache_data['embeddings'])
                    
                    with open(CACHE_PATH, 'wb') as f:
                        pickle.dump(cache_data, f)
                    
                    logger.info(f"✅ Embedding atualizado: {func.nome}")
                    return True
                    
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar embedding: {e}")
            return False
    
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
