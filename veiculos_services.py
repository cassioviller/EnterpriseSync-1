# ================================
# SERVIÇOS DO MÓDULO DE VEÍCULOS V2.0
# ================================
# Services modernos com formulários unificados e design consistente
# Design visual idêntico aos módulos RDO/Obras

from datetime import datetime, date, time, timedelta
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import joinedload
from flask import flash
from models import db, Veiculo, UsoVeiculo, CustoVeiculo, Funcionario, Obra, Usuario
from utils.circuit_breaker import circuit_breaker
from decimal import Decimal


class VeiculoService:
    """Serviço principal para gestão de veículos"""
    
    @staticmethod
    @circuit_breaker('veiculo_list_query', failure_threshold=3, recovery_timeout=60)
    def listar_veiculos(admin_id, filtros=None, page=1, per_page=20):
        """
        Lista veículos com filtros e paginação
        
        Args:
            admin_id: ID do admin (multi-tenant)
            filtros: dict com filtros opcionais (status, tipo, placa)
            page: página atual
            per_page: itens por página
            
        Returns:
            dict com veículos, paginação e estatísticas
        """
        try:
            query = Veiculo.query.filter_by(admin_id=admin_id, ativo=True)
            
            # Aplicar filtros
            if filtros:
                if filtros.get('status'):
                    query = query.filter(Veiculo.status == filtros['status'])
                if filtros.get('tipo'):
                    query = query.filter(Veiculo.tipo == filtros['tipo'])
                if filtros.get('placa'):
                    query = query.filter(Veiculo.placa.ilike(f"%{filtros['placa']}%"))
                if filtros.get('marca'):
                    query = query.filter(Veiculo.marca.ilike(f"%{filtros['marca']}%"))
            
            # Paginação
            pagination = query.order_by(Veiculo.placa).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Estatísticas gerais
            stats = VeiculoService._calcular_estatisticas_gerais(admin_id)
            
            return {
                'veiculos': pagination.items,
                'pagination': pagination,
                'stats': stats,
                'filtros_aplicados': filtros or {}
            }
            
        except Exception as e:
            print(f"❌ Erro ao listar veículos: {str(e)}")
            return {
                'veiculos': [],
                'pagination': None,
                'stats': {},
                'error': str(e)
            }
    
    @staticmethod
    def _calcular_estatisticas_gerais(admin_id):
        """Calcula estatísticas gerais da frota"""
        try:
            total_veiculos = Veiculo.query.filter_by(admin_id=admin_id, ativo=True).count()
            disponveis = Veiculo.query.filter_by(admin_id=admin_id, ativo=True, status='Disponível').count()
            em_uso = Veiculo.query.filter_by(admin_id=admin_id, ativo=True, status='Em Uso').count()
            manutencao = Veiculo.query.filter_by(admin_id=admin_id, ativo=True, status='Manutenção').count()
            
            return {
                'total_veiculos': total_veiculos,
                'disponiveis': disponveis,
                'em_uso': em_uso,
                'manutencao': manutencao,
                'taxa_disponibilidade': round((disponveis / total_veiculos * 100) if total_veiculos > 0 else 0, 1)
            }
        except Exception:
            return {
                'total_veiculos': 0,
                'disponiveis': 0,
                'em_uso': 0,
                'manutencao': 0,
                'taxa_disponibilidade': 0
            }
    
    @staticmethod
    def criar_veiculo(dados, admin_id):
        """
        Cria novo veículo com validações
        
        Args:
            dados: dict com dados do veículo
            admin_id: ID do admin (multi-tenant)
            
        Returns:
            tuple (sucesso: bool, veiculo/erro: Veiculo/str, mensagem: str)
        """
        try:
            # Validar placa única para o admin
            if Veiculo.query.filter_by(admin_id=admin_id, placa=dados['placa']).first():
                return False, None, f"Placa {dados['placa']} já está cadastrada"
            
            veiculo = Veiculo(
                placa=dados['placa'].upper().strip(),
                marca=dados['marca'].strip(),
                modelo=dados['modelo'].strip(),
                ano=int(dados['ano']),
                tipo=dados.get('tipo', 'Utilitário'),
                km_atual=int(dados.get('km_atual', 0)),
                cor=dados.get('cor', '').strip() if dados.get('cor') else None,
                chassi=dados.get('chassi', '').strip() if dados.get('chassi') else None,
                renavam=dados.get('renavam', '').strip() if dados.get('renavam') else None,
                combustivel=dados.get('combustivel', 'Gasolina'),
                status=dados.get('status', 'Disponível'),
                data_ultima_manutencao=dados.get('data_ultima_manutencao') if dados.get('data_ultima_manutencao') else None,
                data_proxima_manutencao=dados.get('data_proxima_manutencao') if dados.get('data_proxima_manutencao') else None,
                km_proxima_manutencao=int(dados['km_proxima_manutencao']) if dados.get('km_proxima_manutencao') else None,
                admin_id=admin_id
            )
            
            db.session.add(veiculo)
            db.session.commit()
            
            return True, veiculo, f"Veículo {veiculo.placa} cadastrado com sucesso"
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar veículo: {str(e)}")
            return False, None, f"Erro ao cadastrar veículo: {str(e)}"
    
    @staticmethod
    def atualizar_veiculo(veiculo_id, dados, admin_id):
        """
        Atualiza dados do veículo
        
        Args:
            veiculo_id: ID do veículo
            dados: dict com novos dados
            admin_id: ID do admin (multi-tenant)
            
        Returns:
            tuple (sucesso: bool, veiculo/erro: Veiculo/str, mensagem: str)
        """
        try:
            veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=admin_id).first()
            if not veiculo:
                return False, None, "Veículo não encontrado"
            
            # Validar placa única (exceto o próprio veículo)
            if dados.get('placa') and dados['placa'] != veiculo.placa:
                if Veiculo.query.filter(
                    Veiculo.admin_id == admin_id,
                    Veiculo.placa == dados['placa'],
                    Veiculo.id != veiculo_id
                ).first():
                    return False, None, f"Placa {dados['placa']} já está cadastrada"
            
            # Atualizar campos
            for campo, valor in dados.items():
                if hasattr(veiculo, campo):
                    if campo == 'placa' and valor:
                        setattr(veiculo, campo, valor.upper().strip())
                    elif campo in ['marca', 'modelo'] and valor:
                        setattr(veiculo, campo, valor.strip())
                    elif campo in ['ano', 'km_atual', 'km_proxima_manutencao'] and valor:
                        setattr(veiculo, campo, int(valor))
                    else:
                        setattr(veiculo, campo, valor)
            
            veiculo.updated_at = datetime.utcnow()
            db.session.commit()
            
            return True, veiculo, f"Veículo {veiculo.placa} atualizado com sucesso"
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao atualizar veículo: {str(e)}")
            return False, None, f"Erro ao atualizar veículo: {str(e)}"


class UsoVeiculoService:
    """Serviço para gestão de uso de veículos com formulários unificados"""
    
    @staticmethod
    def criar_uso_veiculo(dados, admin_id):
        """
        Cria novo registro de uso com campos unificados de custos
        
        Args:
            dados: dict com dados do uso
            admin_id: ID do admin (multi-tenant)
            
        Returns:
            tuple (sucesso: bool, uso/erro: UsoVeiculo/str, mensagem: str)
        """
        try:
            # Validações básicas
            veiculo = Veiculo.query.filter_by(id=dados['veiculo_id'], admin_id=admin_id).first()
            if not veiculo:
                return False, None, "Veículo não encontrado"
            
            # Motorista opcional (novo campo substitui funcionario_id)
            motorista = None
            if dados.get('motorista_id'):
                motorista = Funcionario.query.filter_by(id=dados['motorista_id'], admin_id=admin_id).first()
            
            # Validar obra se informada
            obra = None
            if dados.get('obra_id'):
                obra = Obra.query.filter_by(id=dados['obra_id'], admin_id=admin_id).first()
                if not obra:
                    return False, None, "Obra não encontrada"
            
            # Criar registro de uso
            uso = UsoVeiculo(
                veiculo_id=dados['veiculo_id'],
                funcionario_id=dados.get('motorista_id'),  # Agora opcional
                obra_id=dados.get('obra_id'),
                data_uso=dados['data_uso'],
                hora_saida=dados['hora_saida'],
                hora_retorno=dados.get('hora_retorno'),
                km_inicial=int(dados['km_inicial']),
                km_final=int(dados['km_final']) if dados.get('km_final') else None,
                finalidade=dados['finalidade'].strip(),
                destino=dados.get('destino', '').strip() if dados.get('destino') else None,
                rota_detalhada=dados.get('rota_detalhada', '').strip() if dados.get('rota_detalhada') else None,
                
                # Campos unificados de custos
                valor_combustivel=Decimal(str(dados.get('valor_combustivel', 0))) if dados.get('valor_combustivel') else Decimal('0'),
                litros_combustivel=Decimal(str(dados.get('litros_combustivel', 0))) if dados.get('litros_combustivel') else Decimal('0'),
                valor_pedagio=Decimal(str(dados.get('valor_pedagio', 0))) if dados.get('valor_pedagio') else Decimal('0'),
                valor_manutencao=Decimal(str(dados.get('valor_manutencao', 0))) if dados.get('valor_manutencao') else Decimal('0'),
                valor_outros=Decimal(str(dados.get('valor_outros', 0))) if dados.get('valor_outros') else Decimal('0'),
                
                status=dados.get('status', 'Em Andamento'),
                responsavel_veiculo=dados.get('responsavel_veiculo', motorista.nome if motorista else 'Não informado'),
                observacoes=dados.get('observacoes', '').strip() if dados.get('observacoes') else None,
                admin_id=admin_id
            )
            
            # Calcular KM percorrido automaticamente
            uso.calcular_km_percorrido()
            
            db.session.add(uso)
            
            # Atualizar status do veículo se necessário
            if veiculo.status == 'Disponível':
                veiculo.status = 'Em Uso'
            
            db.session.commit()
            
            return True, uso, f"Uso do veículo {veiculo.placa} registrado com sucesso"
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar uso de veículo: {str(e)}")
            return False, None, f"Erro ao registrar uso: {str(e)}"
    
    @staticmethod
    def finalizar_uso_veiculo(uso_id, dados_finalizacao, admin_id):
        """
        Finaliza uso do veículo com dados de retorno
        
        Args:
            uso_id: ID do uso
            dados_finalizacao: dict com dados de finalização
            admin_id: ID do admin (multi-tenant)
            
        Returns:
            tuple (sucesso: bool, uso/erro: UsoVeiculo/str, mensagem: str)
        """
        try:
            uso = UsoVeiculo.query.filter_by(id=uso_id, admin_id=admin_id).first()
            if not uso:
                return False, None, "Uso não encontrado"
            
            if uso.status == 'Finalizado':
                return False, None, "Uso já foi finalizado"
            
            # Atualizar dados de finalização
            uso.hora_retorno = dados_finalizacao.get('hora_retorno', time.now())
            uso.km_final = int(dados_finalizacao['km_final'])
            uso.observacoes_retorno = dados_finalizacao.get('observacoes_retorno', '').strip() if dados_finalizacao.get('observacoes_retorno') else None
            uso.status = 'Finalizado'
            
            # Atualizar custos se informados na finalização
            if dados_finalizacao.get('valor_combustivel'):
                uso.valor_combustivel = Decimal(str(dados_finalizacao['valor_combustivel']))
            if dados_finalizacao.get('litros_combustivel'):
                uso.litros_combustivel = Decimal(str(dados_finalizacao['litros_combustivel']))
            if dados_finalizacao.get('valor_pedagio'):
                uso.valor_pedagio = Decimal(str(dados_finalizacao['valor_pedagio']))
            if dados_finalizacao.get('valor_outros'):
                uso.valor_outros = Decimal(str(dados_finalizacao['valor_outros']))
            
            # Recalcular KM percorrido
            uso.calcular_km_percorrido()
            
            # Atualizar KM atual do veículo
            veiculo = uso.veiculo
            if uso.km_final and uso.km_final > veiculo.km_atual:
                veiculo.km_atual = uso.km_final
                veiculo.updated_at = datetime.utcnow()
            
            # Verificar se deve liberar o veículo
            usos_pendentes = UsoVeiculo.query.filter(
                UsoVeiculo.veiculo_id == veiculo.id,
                UsoVeiculo.status == 'Em Andamento',
                UsoVeiculo.id != uso_id
            ).count()
            
            if usos_pendentes == 0:
                veiculo.status = 'Disponível'
            
            uso.updated_at = datetime.utcnow()
            db.session.commit()
            
            return True, uso, f"Uso do veículo {veiculo.placa} finalizado com sucesso"
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao finalizar uso: {str(e)}")
            return False, None, f"Erro ao finalizar uso: {str(e)}"
    
    @staticmethod
    def listar_usos_veiculo(veiculo_id, admin_id, filtros=None, page=1, per_page=20):
        """
        Lista usos de um veículo específico
        
        Args:
            veiculo_id: ID do veículo
            admin_id: ID do admin (multi-tenant)
            filtros: dict com filtros opcionais
            page: página atual
            per_page: itens por página
            
        Returns:
            dict com usos, paginação e estatísticas
        """
        try:
            # Verificar se veículo existe e pertence ao admin
            veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=admin_id).first()
            if not veiculo:
                return {'error': 'Veículo não encontrado'}
            
            query = UsoVeiculo.query.filter_by(veiculo_id=veiculo_id).options(
                joinedload(UsoVeiculo.funcionario),
                joinedload(UsoVeiculo.obra)
            )
            
            # Aplicar filtros
            if filtros:
                if filtros.get('data_inicio'):
                    query = query.filter(UsoVeiculo.data_uso >= filtros['data_inicio'])
                if filtros.get('data_fim'):
                    query = query.filter(UsoVeiculo.data_uso <= filtros['data_fim'])
                if filtros.get('status'):
                    query = query.filter(UsoVeiculo.status == filtros['status'])
                if filtros.get('funcionario_id'):
                    query = query.filter(UsoVeiculo.funcionario_id == filtros['funcionario_id'])
            
            # Paginação
            pagination = query.order_by(desc(UsoVeiculo.data_uso)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Estatísticas do período
            stats = UsoVeiculoService._calcular_estatisticas_uso_veiculo(veiculo_id, filtros)
            
            return {
                'veiculo': veiculo,
                'usos': pagination.items,
                'pagination': pagination,
                'stats': stats,
                'filtros_aplicados': filtros or {}
            }
            
        except Exception as e:
            print(f"❌ Erro ao listar usos do veículo: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _calcular_estatisticas_uso_veiculo(veiculo_id, filtros=None):
        """Calcula estatísticas de uso do veículo"""
        try:
            query = UsoVeiculo.query.filter_by(veiculo_id=veiculo_id)
            
            # Aplicar filtros de data se informados
            if filtros:
                if filtros.get('data_inicio'):
                    query = query.filter(UsoVeiculo.data_uso >= filtros['data_inicio'])
                if filtros.get('data_fim'):
                    query = query.filter(UsoVeiculo.data_uso <= filtros['data_fim'])
            
            usos = query.all()
            
            total_usos = len(usos)
            km_total = sum(uso.km_percorrido for uso in usos if uso.km_percorrido)
            
            custo_total = sum(uso.valor_total_uso for uso in usos)
            combustivel_total = sum(float(uso.valor_combustivel) for uso in usos if uso.valor_combustivel)
            pedagio_total = sum(float(uso.valor_pedagio) for uso in usos if uso.valor_pedagio)
            
            return {
                'total_usos': total_usos,
                'km_total': km_total,
                'custo_total': round(custo_total, 2),
                'combustivel_total': round(combustivel_total, 2),
                'pedagio_total': round(pedagio_total, 2),
                'media_km_por_uso': round(km_total / total_usos, 1) if total_usos > 0 else 0,
                'custo_por_km': round(custo_total / km_total, 2) if km_total > 0 else 0
            }
            
        except Exception:
            return {
                'total_usos': 0,
                'km_total': 0,
                'custo_total': 0,
                'combustivel_total': 0,
                'pedagio_total': 0,
                'media_km_por_uso': 0,
                'custo_por_km': 0
            }


class CustoVeiculoService:
    """Serviço para gestão de custos de veículos (manutenção, seguro, etc.)"""
    
    @staticmethod
    def criar_custo_veiculo(dados, admin_id):
        """
        Cria novo custo para veículo
        
        Args:
            dados: dict com dados do custo
            admin_id: ID do admin (multi-tenant)
            
        Returns:
            tuple (sucesso: bool, custo/erro: CustoVeiculo/str, mensagem: str)
        """
        try:
            # Validar veículo
            veiculo = Veiculo.query.filter_by(id=dados['veiculo_id'], admin_id=admin_id).first()
            if not veiculo:
                return False, None, "Veículo não encontrado"
            
            custo = CustoVeiculo(
                veiculo_id=dados['veiculo_id'],
                data_custo=dados['data_custo'],
                tipo_custo=dados['tipo_custo'],
                categoria=dados.get('categoria', 'operacional'),
                valor=Decimal(str(dados['valor'])),
                descricao=dados['descricao'].strip(),
                fornecedor=dados.get('fornecedor', '').strip() if dados.get('fornecedor') else None,
                numero_nota_fiscal=dados.get('numero_nota_fiscal', '').strip() if dados.get('numero_nota_fiscal') else None,
                data_vencimento=dados.get('data_vencimento'),
                status_pagamento=dados.get('status_pagamento', 'Pendente'),
                forma_pagamento=dados.get('forma_pagamento', '').strip() if dados.get('forma_pagamento') else None,
                km_veiculo=veiculo.km_atual,
                observacoes=dados.get('observacoes', '').strip() if dados.get('observacoes') else None,
                admin_id=admin_id
            )
            
            db.session.add(custo)
            
            # Atualizar data de última manutenção se for manutenção
            if dados['tipo_custo'] == 'manutencao':
                veiculo.data_ultima_manutencao = dados['data_custo']
                veiculo.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return True, custo, f"Custo registrado para o veículo {veiculo.placa}"
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar custo: {str(e)}")
            return False, None, f"Erro ao registrar custo: {str(e)}"
    
    @staticmethod
    def listar_custos_veiculo(veiculo_id, admin_id, filtros=None, page=1, per_page=20):
        """
        Lista custos de um veículo específico
        
        Args:
            veiculo_id: ID do veículo
            admin_id: ID do admin (multi-tenant)
            filtros: dict com filtros opcionais
            page: página atual
            per_page: itens por página
            
        Returns:
            dict com custos, paginação e estatísticas
        """
        try:
            # Verificar se veículo existe
            veiculo = Veiculo.query.filter_by(id=veiculo_id, admin_id=admin_id).first()
            if not veiculo:
                return {'error': 'Veículo não encontrado'}
            
            query = CustoVeiculo.query.filter_by(veiculo_id=veiculo_id)
            
            # Aplicar filtros
            if filtros:
                if filtros.get('data_inicio'):
                    query = query.filter(CustoVeiculo.data_custo >= filtros['data_inicio'])
                if filtros.get('data_fim'):
                    query = query.filter(CustoVeiculo.data_custo <= filtros['data_fim'])
                if filtros.get('tipo_custo'):
                    query = query.filter(CustoVeiculo.tipo_custo == filtros['tipo_custo'])
                if filtros.get('status_pagamento'):
                    query = query.filter(CustoVeiculo.status_pagamento == filtros['status_pagamento'])
            
            # Paginação
            pagination = query.order_by(desc(CustoVeiculo.data_custo)).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Estatísticas
            stats = CustoVeiculoService._calcular_estatisticas_custo_veiculo(veiculo_id, filtros)
            
            return {
                'veiculo': veiculo,
                'custos': pagination.items,
                'pagination': pagination,
                'stats': stats,
                'filtros_aplicados': filtros or {}
            }
            
        except Exception as e:
            print(f"❌ Erro ao listar custos: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _calcular_estatisticas_custo_veiculo(veiculo_id, filtros=None):
        """Calcula estatísticas de custos do veículo"""
        try:
            query = CustoVeiculo.query.filter_by(veiculo_id=veiculo_id)
            
            # Aplicar filtros de data se informados
            if filtros:
                if filtros.get('data_inicio'):
                    query = query.filter(CustoVeiculo.data_custo >= filtros['data_inicio'])
                if filtros.get('data_fim'):
                    query = query.filter(CustoVeiculo.data_custo <= filtros['data_fim'])
            
            custos = query.all()
            
            total_custos = len(custos)
            valor_total = sum(float(custo.valor) for custo in custos)
            valor_manutencao = sum(float(custo.valor) for custo in custos if custo.tipo_custo == 'manutencao')
            valor_seguro = sum(float(custo.valor) for custo in custos if custo.tipo_custo == 'seguro')
            valor_multas = sum(float(custo.valor) for custo in custos if custo.tipo_custo == 'multa')
            custos_pendentes = sum(float(custo.valor) for custo in custos if custo.status_pagamento == 'Pendente')
            
            return {
                'total_custos': total_custos,
                'valor_total': round(valor_total, 2),
                'valor_manutencao': round(valor_manutencao, 2),
                'valor_seguro': round(valor_seguro, 2),
                'valor_multas': round(valor_multas, 2),
                'custos_pendentes': round(custos_pendentes, 2),
                'percentual_manutencao': round((valor_manutencao / valor_total * 100) if valor_total > 0 else 0, 1)
            }
            
        except Exception:
            return {
                'total_custos': 0,
                'valor_total': 0,
                'valor_manutencao': 0,
                'valor_seguro': 0,
                'valor_multas': 0,
                'custos_pendentes': 0,
                'percentual_manutencao': 0
            }