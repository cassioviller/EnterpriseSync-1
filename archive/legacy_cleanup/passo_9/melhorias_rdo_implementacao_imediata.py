# MELHORIAS RDO - IMPLEMENTAÇÃO IMEDIATA
# Script para implementar as correções mais críticas do sistema RDO

from flask import Flask, request, jsonify, flash
from datetime import datetime, date, timedelta
import json
from typing import Dict, List, Optional, Tuple

class RDOValidator:
    """Sistema de validações robusto para RDO"""
    
    @staticmethod
    def validar_rdo_unico_por_dia(obra_id: int, data_relatorio: date, rdo_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Valida se já existe RDO para a data/obra
        Retorna: (is_valid, error_message)
        """
        from models import RDO
        
        query = RDO.query.filter_by(obra_id=obra_id, data_relatorio=data_relatorio)
        if rdo_id:
            query = query.filter(RDO.id != rdo_id)
        
        rdo_existente = query.first()
        if rdo_existente:
            return False, f"Já existe RDO {rdo_existente.numero_rdo} para esta obra na data {data_relatorio.strftime('%d/%m/%Y')}"
        
        return True, ""
    
    @staticmethod
    def validar_horas_funcionario_dia(funcionario_id: int, data_trabalho: date, horas_trabalhadas: float, rdo_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Valida se funcionário não excede 12h de trabalho por dia
        """
        from models import RDOMaoObra, RDO
        
        # Buscar total de horas do funcionário na data
        query = db.session.query(
            db.func.sum(RDOMaoObra.horas_trabalhadas)
        ).join(RDO).filter(
            RDOMaoObra.funcionario_id == funcionario_id,
            RDO.data_relatorio == data_trabalho
        )
        
        if rdo_id:
            query = query.filter(RDO.id != rdo_id)
        
        total_horas_existentes = query.scalar() or 0
        total_com_novas = total_horas_existentes + horas_trabalhadas
        
        if total_com_novas > 12:
            return False, f"Funcionário excederia {total_com_novas}h de trabalho (máximo 12h/dia). Já possui {total_horas_existentes}h registradas."
        
        return True, ""
    
    @staticmethod
    def validar_percentual_atividade(percentual: float) -> Tuple[bool, str]:
        """Valida se percentual está entre 0-100"""
        if not (0 <= percentual <= 100):
            return False, f"Percentual deve estar entre 0% e 100%. Valor informado: {percentual}%"
        return True, ""
    
    @staticmethod
    def validar_equipamento_disponibilidade(nome_equipamento: str, obra_id: int, data_uso: date, horas_uso: float, rdo_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Valida se equipamento não está sendo usado em excesso
        Considera disponibilidade de 24h por dia por equipamento
        """
        from models import RDOEquipamento, RDO
        
        # Buscar total de horas do equipamento na data/obra
        query = db.session.query(
            db.func.sum(RDOEquipamento.horas_uso)
        ).join(RDO).filter(
            RDOEquipamento.nome_equipamento.ilike(f'%{nome_equipamento}%'),
            RDO.obra_id == obra_id,
            RDO.data_relatorio == data_uso
        )
        
        if rdo_id:
            query = query.filter(RDO.id != rdo_id)
        
        total_horas_existentes = query.scalar() or 0
        total_com_novas = total_horas_existentes + horas_uso
        
        if total_com_novas > 24:
            return False, f"Equipamento '{nome_equipamento}' excederia {total_com_novas}h de uso (máximo 24h/dia). Já possui {total_horas_existentes}h registradas."
        
        return True, ""
    
    @staticmethod
    def validar_data_relatorio(data_relatorio: date) -> Tuple[bool, str]:
        """Valida se data do relatório não é futura ou muito antiga"""
        hoje = date.today()
        
        if data_relatorio > hoje:
            return False, "Data do relatório não pode ser futura"
        
        # Não permitir RDO muito antigo (mais de 30 dias)
        limite_passado = hoje - timedelta(days=30)
        if data_relatorio < limite_passado:
            return False, f"Data do relatório muito antiga. Limite: {limite_passado.strftime('%d/%m/%Y')}"
        
        return True, ""

class RDOAutoSave:
    """Sistema de auto-save para RDO"""
    
    @staticmethod
    def save_draft(user_id: int, obra_id: int, form_data: Dict) -> bool:
        """Salva rascunho do RDO em cache"""
        try:
            draft_key = f"rdo_draft_{user_id}_{obra_id}"
            draft_data = {
                'form_data': form_data,
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'obra_id': obra_id
            }
            
            # Salvar em cache (Redis idealmente, localStorage como fallback)
            cache.set(draft_key, json.dumps(draft_data), timeout=86400)  # 24h
            return True
        except Exception as e:
            print(f"Erro ao salvar rascunho: {e}")
            return False
    
    @staticmethod
    def load_draft(user_id: int, obra_id: int) -> Optional[Dict]:
        """Carrega rascunho do RDO"""
        try:
            draft_key = f"rdo_draft_{user_id}_{obra_id}"
            draft_json = cache.get(draft_key)
            
            if draft_json:
                return json.loads(draft_json)
            return None
        except Exception as e:
            print(f"Erro ao carregar rascunho: {e}")
            return None
    
    @staticmethod
    def clear_draft(user_id: int, obra_id: int) -> bool:
        """Remove rascunho após salvar RDO final"""
        try:
            draft_key = f"rdo_draft_{user_id}_{obra_id}"
            cache.delete(draft_key)
            return True
        except Exception as e:
            print(f"Erro ao limpar rascunho: {e}")
            return False

class RDOProgressTracker:
    """Sistema de acompanhamento de progresso de atividades"""
    
    @staticmethod
    def calcular_progresso_obra(obra_id: int) -> Dict:
        """Calcula progresso geral da obra baseado nos RDOs"""
        from models import RDOAtividade, RDO
        
        # Buscar todas as atividades da obra
        atividades = db.session.query(RDOAtividade).join(RDO).filter(
            RDO.obra_id == obra_id,
            RDO.status == 'Finalizado'
        ).all()
        
        if not atividades:
            return {'progresso_geral': 0, 'total_atividades': 0}
        
        # Agrupar por tipo de atividade e pegar maior percentual
        atividades_max = {}
        for atividade in atividades:
            desc = atividade.descricao_atividade.lower().strip()
            if desc not in atividades_max:
                atividades_max[desc] = atividade.percentual_conclusao
            else:
                atividades_max[desc] = max(atividades_max[desc], atividade.percentual_conclusao)
        
        # Calcular média ponderada
        progresso_medio = sum(atividades_max.values()) / len(atividades_max)
        
        return {
            'progresso_geral': round(progresso_medio, 2),
            'total_atividades': len(atividades_max),
            'atividades_detalhes': atividades_max
        }
    
    @staticmethod
    def identificar_atividades_atrasadas(obra_id: int, limite_dias: int = 7) -> List[Dict]:
        """Identifica atividades sem progresso há X dias"""
        from models import RDOAtividade, RDO
        
        data_limite = date.today() - timedelta(days=limite_dias)
        
        # Buscar atividades que não tiveram progresso recente
        atividades_recentes = db.session.query(RDOAtividade).join(RDO).filter(
            RDO.obra_id == obra_id,
            RDO.data_relatorio >= data_limite,
            RDOAtividade.percentual_conclusao < 100
        ).all()
        
        # Agrupar e verificar progresso
        atividades_sem_progresso = []
        for atividade in atividades_recentes:
            # Verificar se houve progresso nos últimos dias
            progresso_anterior = db.session.query(RDOAtividade).join(RDO).filter(
                RDO.obra_id == obra_id,
                RDO.data_relatorio < data_limite,
                RDOAtividade.descricao_atividade == atividade.descricao_atividade
            ).order_by(RDO.data_relatorio.desc()).first()
            
            if progresso_anterior and atividade.percentual_conclusao <= progresso_anterior.percentual_conclusao:
                atividades_sem_progresso.append({
                    'descricao': atividade.descricao_atividade,
                    'percentual_atual': atividade.percentual_conclusao,
                    'dias_sem_progresso': (date.today() - atividade.rdo_ref.data_relatorio).days
                })
        
        return atividades_sem_progresso

class RDONotificationService:
    """Sistema de notificações para RDO"""
    
    @staticmethod
    def verificar_rdo_pendente(obra_id: int, data_verificacao: date = None) -> Dict:
        """Verifica se RDO está pendente para a data"""
        if not data_verificacao:
            data_verificacao = date.today()
        
        from models import RDO
        
        rdo_existente = RDO.query.filter_by(
            obra_id=obra_id,
            data_relatorio=data_verificacao
        ).first()
        
        return {
            'pendente': rdo_existente is None,
            'data': data_verificacao.isoformat(),
            'obra_id': obra_id,
            'rdo_existente': rdo_existente.numero_rdo if rdo_existente else None
        }
    
    @staticmethod
    def gerar_alertas_obra(obra_id: int) -> List[Dict]:
        """Gera lista de alertas para a obra"""
        alertas = []
        
        # Verificar RDO pendente hoje
        rdo_pendente = RDONotificationService.verificar_rdo_pendente(obra_id)
        if rdo_pendente['pendente']:
            alertas.append({
                'tipo': 'rdo_pendente',
                'severidade': 'warning',
                'titulo': 'RDO Pendente',
                'mensagem': f'RDO não foi criado para hoje ({date.today().strftime("%d/%m/%Y")})',
                'acao': 'criar_rdo'
            })
        
        # Verificar atividades atrasadas
        atividades_atrasadas = RDOProgressTracker.identificar_atividades_atrasadas(obra_id)
        if atividades_atrasadas:
            alertas.append({
                'tipo': 'atividades_atrasadas',
                'severidade': 'error',
                'titulo': 'Atividades Sem Progresso',
                'mensagem': f'{len(atividades_atrasadas)} atividades sem progresso há mais de 7 dias',
                'detalhes': atividades_atrasadas
            })
        
        return alertas

# JAVASCRIPT PARA AUTO-SAVE (para incluir nos templates)
AUTO_SAVE_JAVASCRIPT = """
<script>
class RDOAutoSave {
    constructor(obraId, userId) {
        this.obraId = obraId;
        this.userId = userId;
        this.hasUnsavedChanges = false;
        this.autoSaveInterval = null;
        this.lastSaveTime = null;
        
        this.initializeAutoSave();
        this.loadDraft();
    }
    
    initializeAutoSave() {
        // Auto-save a cada 30 segundos
        this.autoSaveInterval = setInterval(() => {
            if (this.hasUnsavedChanges) {
                this.saveDraft();
            }
        }, 30000);
        
        // Detectar mudanças no formulário
        document.addEventListener('input', (e) => {
            if (e.target.form && e.target.form.id === 'rdo-form') {
                this.hasUnsavedChanges = true;
                this.showUnsavedIndicator();
            }
        });
        
        // Salvar antes de sair da página
        window.addEventListener('beforeunload', (e) => {
            if (this.hasUnsavedChanges) {
                this.saveDraft();
                e.returnValue = 'Você tem alterações não salvas. Deseja sair mesmo assim?';
            }
        });
    }
    
    collectFormData() {
        const form = document.getElementById('rdo-form');
        if (!form) return {};
        
        const formData = new FormData(form);
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            if (data[key]) {
                // Múltiplos valores para o mesmo campo (checkboxes, etc.)
                if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            } else {
                data[key] = value;
            }
        }
        
        return data;
    }
    
    async saveDraft() {
        try {
            const formData = this.collectFormData();
            
            const response = await fetch('/api/rdo/save-draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    obra_id: this.obraId,
                    form_data: formData
                })
            });
            
            if (response.ok) {
                this.hasUnsavedChanges = false;
                this.lastSaveTime = new Date();
                this.showSavedIndicator();
            }
        } catch (error) {
            console.error('Erro ao salvar rascunho:', error);
            this.showErrorIndicator();
        }
    }
    
    async loadDraft() {
        try {
            const response = await fetch(`/api/rdo/load-draft/${this.obraId}`);
            
            if (response.ok) {
                const draft = await response.json();
                if (draft && draft.form_data) {
                    this.populateForm(draft.form_data);
                    this.showDraftLoadedIndicator();
                }
            }
        } catch (error) {
            console.error('Erro ao carregar rascunho:', error);
        }
    }
    
    populateForm(formData) {
        for (let [key, value] of Object.entries(formData)) {
            const element = document.querySelector(`[name="${key}"]`);
            if (element) {
                if (element.type === 'checkbox' || element.type === 'radio') {
                    element.checked = value === element.value;
                } else {
                    element.value = value;
                }
            }
        }
    }
    
    showUnsavedIndicator() {
        const indicator = document.getElementById('save-indicator');
        if (indicator) {
            indicator.innerHTML = '<i class="fas fa-exclamation-triangle text-warning"></i> Alterações não salvas';
            indicator.className = 'alert alert-warning alert-sm';
        }
    }
    
    showSavedIndicator() {
        const indicator = document.getElementById('save-indicator');
        if (indicator) {
            indicator.innerHTML = `<i class="fas fa-check text-success"></i> Salvo automaticamente ${this.lastSaveTime.toLocaleTimeString()}`;
            indicator.className = 'alert alert-success alert-sm';
            
            // Esconder após 3 segundos
            setTimeout(() => {
                indicator.innerHTML = '';
                indicator.className = '';
            }, 3000);
        }
    }
    
    showDraftLoadedIndicator() {
        const indicator = document.getElementById('save-indicator');
        if (indicator) {
            indicator.innerHTML = '<i class="fas fa-info-circle text-info"></i> Rascunho anterior carregado';
            indicator.className = 'alert alert-info alert-sm';
        }
    }
    
    showErrorIndicator() {
        const indicator = document.getElementById('save-indicator');
        if (indicator) {
            indicator.innerHTML = '<i class="fas fa-times text-danger"></i> Erro ao salvar';
            indicator.className = 'alert alert-danger alert-sm';
        }
    }
    
    clearDraft() {
        fetch(`/api/rdo/clear-draft/${this.obraId}`, { method: 'DELETE' });
        this.hasUnsavedChanges = false;
    }
    
    destroy() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
        }
    }
}

// Inicializar auto-save quando página carregar
document.addEventListener('DOMContentLoaded', function() {
    const obraId = document.querySelector('[name="obra_id"]')?.value;
    const userId = document.querySelector('[data-user-id]')?.dataset.userId;
    
    if (obraId && userId) {
        window.rdoAutoSave = new RDOAutoSave(obraId, userId);
    }
});
</script>
"""