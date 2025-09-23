"""
🚗 VEHICLE USAGE SERVICE - Serviço de Uso de Veículos
====================================================
Camada de serviço para operações com uso de veículos
Implementa eager loading, isolamento tenant e otimizações de query
"""

from flask import current_app
from sqlalchemy.orm import joinedload
from sqlalchemy import desc, asc, func, text
from models import db, UsoVeiculo, PassageiroVeiculo, CustoVeiculo, Veiculo, Funcionario, Obra
from utils.tenant import get_tenant_admin_id
from datetime import datetime, date


class VehicleUsageService:
    """Serviço centralizado para operações de uso de veículos"""
    
    @staticmethod
    def get_vehicle_with_security(veiculo_id, admin_id=None):
        """Buscar veículo com verificação de segurança"""
        if not admin_id:
            admin_id = get_tenant_admin_id()
        
        if not admin_id:
            return None
        
        # 🔧 CORREÇÃO CRÍTICA: Garantir conversão de tipo
        try:
            veiculo_id = int(veiculo_id)
            admin_id = int(admin_id)
        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Erro conversão tipo veiculo_id={veiculo_id}, admin_id={admin_id}: {e}")
            return None
            
        return Veiculo.query.filter_by(
            id=veiculo_id, 
            admin_id=admin_id,
            ativo=True
        ).first()
    
    @staticmethod
    def get_usage_with_details(uso_id, admin_id=None):
        """Buscar uso específico com todos os relacionamentos carregados"""
        if not admin_id:
            admin_id = get_tenant_admin_id()
        
        if not admin_id:
            return None
        
        # 🔧 CORREÇÃO CRÍTICA: Garantir conversão de tipo
        try:
            uso_id = int(uso_id)
            admin_id = int(admin_id)
        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Erro conversão tipo uso_id={uso_id}, admin_id={admin_id}: {e}")
            return None
            
        # Query otimizada com eager loading
        uso = UsoVeiculo.query.options(
            joinedload(UsoVeiculo.veiculo),
            joinedload(UsoVeiculo.funcionario).joinedload('funcao_ref'),
            joinedload(UsoVeiculo.obra)
        ).filter_by(
            id=uso_id,
            admin_id=admin_id
        ).first()
        
        return uso
    
    @staticmethod
    def get_usage_passengers(uso_id, admin_id=None):
        """Buscar passageiros de um uso específico"""
        if not admin_id:
            admin_id = get_tenant_admin_id()
        
        if not admin_id:
            return []
            
        passageiros = PassageiroVeiculo.query.options(
            joinedload(PassageiroVeiculo.funcionario).joinedload('funcao_ref')
        ).filter_by(
            uso_veiculo_id=uso_id,
            admin_id=admin_id
        ).order_by(PassageiroVeiculo.posicao, PassageiroVeiculo.funcionario_id).all()
        
        return passageiros
    
    @staticmethod
    def get_vehicle_usage_list(veiculo_id, page=1, per_page=20, admin_id=None):
        """Buscar lista paginada de usos de um veículo"""
        if not admin_id:
            admin_id = get_tenant_admin_id()
        
        if not admin_id:
            return None
        
        # 🔧 CORREÇÃO CRÍTICA: Garantir conversão de tipo
        try:
            veiculo_id = int(veiculo_id)
            admin_id = int(admin_id)
            page = int(page)
            per_page = int(per_page)
        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Erro conversão tipo: veiculo_id={veiculo_id}, admin_id={admin_id}, page={page}: {e}")
            return None
            
        # Verificar se veículo pertence ao admin
        veiculo = VehicleUsageService.get_vehicle_with_security(veiculo_id, admin_id)
        if not veiculo:
            return None
        
        # Query paginada com eager loading
        usos_query = UsoVeiculo.query.options(
            joinedload(UsoVeiculo.funcionario),
            joinedload(UsoVeiculo.obra)
        ).filter_by(
            veiculo_id=veiculo_id,
            admin_id=admin_id
        ).order_by(desc(UsoVeiculo.data_uso), desc(UsoVeiculo.id))
        
        pagination = usos_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return {
            'veiculo': veiculo,
            'usos': pagination.items,
            'pagination': pagination,
            'total': pagination.total
        }
    
    @staticmethod
    def get_vehicle_usage_stats(veiculo_id, admin_id=None):
        """Calcular estatísticas de uso do veículo"""
        if not admin_id:
            admin_id = get_tenant_admin_id()
        
        if not admin_id:
            return {}
        
        try:
            # Estatísticas gerais usando SQL otimizado
            # 🔧 CORREÇÃO CRÍTICA: Garantir conversão de tipo para query SQL
            try:
                veiculo_id = int(veiculo_id)
                admin_id = int(admin_id)
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"Erro conversão tipo stats: veiculo_id={veiculo_id}, admin_id={admin_id}: {e}")
                return {}
            
            stats_result = db.session.execute(text("""
                SELECT 
                    COUNT(*) as total_usos,
                    COALESCE(SUM(km_final - km_inicial), 0) as km_total,
                    COALESCE(AVG(km_final - km_inicial), 0) as km_medio,
                    COALESCE(MAX(km_final), 0) as km_atual,
                    COUNT(DISTINCT funcionario_id) as condutores_diferentes
                FROM uso_veiculo 
                WHERE veiculo_id = :veiculo_id 
                  AND admin_id = :admin_id
                  AND km_inicial IS NOT NULL 
                  AND km_final IS NOT NULL
            """), {
                'veiculo_id': veiculo_id,
                'admin_id': admin_id
            }).fetchone()
            
            # Estatísticas de passageiros
            passageiros_result = db.session.execute(text("""
                SELECT COUNT(*) as total_passageiros
                FROM passageiro_veiculo pv
                JOIN uso_veiculo uv ON pv.uso_veiculo_id = uv.id
                WHERE uv.veiculo_id = :veiculo_id 
                  AND pv.admin_id = :admin_id
            """), {
                'veiculo_id': veiculo_id,
                'admin_id': admin_id
            }).fetchone()
            
            return {
                'total_usos': stats_result[0] or 0,
                'km_total': float(stats_result[1] or 0),
                'km_medio': float(stats_result[2] or 0),
                'km_atual': int(stats_result[3] or 0),
                'condutores_diferentes': stats_result[4] or 0,
                'total_passageiros': passageiros_result[0] or 0
            }
            
        except Exception as e:
            current_app.logger.error(f"Erro ao calcular estatísticas: {e}")
            return {}
    
    @staticmethod
    def organize_passengers_by_position(passageiros):
        """Organizar passageiros por posição no veículo"""
        passageiros_frente = [p for p in passageiros if p.posicao == 'frente']
        passageiros_tras = [p for p in passageiros if p.posicao == 'tras']
        
        return {
            'frente': passageiros_frente,
            'tras': passageiros_tras,
            'total': len(passageiros)
        }
    
    @staticmethod
    def get_vehicle_costs_summary(veiculo_id, admin_id=None):
        """Buscar resumo de custos do veículo"""
        if not admin_id:
            admin_id = get_tenant_admin_id()
        
        if not admin_id:
            return {}
            
        try:
            # 🔧 CORREÇÃO CRÍTICA: Garantir conversão de tipo para query SQL
            try:
                veiculo_id = int(veiculo_id)
                admin_id = int(admin_id)
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"Erro conversão tipo costs: veiculo_id={veiculo_id}, admin_id={admin_id}: {e}")
                return {}
            
            costs_result = db.session.execute(text("""
                SELECT 
                    tipo_custo,
                    COUNT(*) as quantidade,
                    COALESCE(SUM(valor), 0) as valor_total
                FROM custo_veiculo 
                WHERE veiculo_id = :veiculo_id 
                  AND admin_id = :admin_id
                GROUP BY tipo_custo
                ORDER BY valor_total DESC
            """), {
                'veiculo_id': veiculo_id,
                'admin_id': admin_id
            }).fetchall()
            
            costs_by_type = {}
            total_geral = 0
            
            for row in costs_result:
                tipo, quantidade, valor = row
                costs_by_type[tipo] = {
                    'quantidade': quantidade,
                    'valor_total': float(valor),
                    'valor_medio': float(valor) / quantidade if quantidade > 0 else 0
                }
                total_geral += float(valor)
            
            return {
                'por_tipo': costs_by_type,
                'total_geral': total_geral,
                'tipos_count': len(costs_by_type)
            }
            
        except Exception as e:
            current_app.logger.error(f"Erro ao calcular custos: {e}")
            return {}