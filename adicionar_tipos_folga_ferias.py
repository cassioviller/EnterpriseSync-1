#!/usr/bin/env python3
"""
ADICIONAR TIPOS DE FOLGA E FÉRIAS - SIGE v8.1
Adiciona tipos sabado_folga, domingo_folga, ferias e cria registros automáticos
"""

from app import app, db
from models import *
from datetime import date, datetime, timedelta
from sqlalchemy import func, and_, or_
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def criar_registros_folga_vale_verde():
    """Cria registros de folga para funcionários da Vale Verde"""
    
    print("CRIANDO REGISTROS DE FOLGA - VALE VERDE")
    print("=" * 60)
    
    # Buscar funcionários da Vale Verde
    funcionarios_vale_verde = Funcionario.query.filter(
        and_(
            Funcionario.ativo == True,
            Funcionario.nome.contains('Vale Verde')  # Por nome
        )
    ).all()
    
    if not funcionarios_vale_verde:
        # Buscar funcionários que trabalham na obra Vale Verde
        obras_vale_verde = Obra.query.filter(
            Obra.nome.contains('Vale Verde')
        ).all()
        
        if obras_vale_verde:
            funcionarios_vale_verde = []
            for obra in obras_vale_verde:
                funcionarios_obra = db.session.query(Funcionario).join(RegistroPonto).filter(
                    RegistroPonto.obra_id == obra.id
                ).distinct().all()
                funcionarios_vale_verde.extend(funcionarios_obra)
        
        # Remover duplicatas
        funcionarios_vale_verde = list(set(funcionarios_vale_verde))
    
    print(f"Funcionários Vale Verde encontrados: {len(funcionarios_vale_verde)}")
    
    # Período para criar folgas (últimos 3 meses)
    data_fim = date.today()
    data_inicio = date(2025, 5, 1)  # Maio a hoje
    
    registros_criados = 0
    registros_ferias = 0
    
    for funcionario in funcionarios_vale_verde:
        print(f"\nProcessando: {funcionario.nome}")
        
        # Percorrer cada dia do período
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            dia_semana = data_atual.weekday()  # 0=Segunda, 6=Domingo
            
            # Verificar se é sábado ou domingo
            if dia_semana in [5, 6]:  # Sábado=5, Domingo=6
                # Verificar se já existe registro para o dia
                registro_existente = RegistroPonto.query.filter(
                    RegistroPonto.funcionario_id == funcionario.id,
                    RegistroPonto.data == data_atual
                ).first()
                
                if not registro_existente:
                    # Determinar tipo de folga
                    if dia_semana == 5:  # Sábado
                        tipo_folga = 'sabado_folga'
                    else:  # Domingo
                        tipo_folga = 'domingo_folga'
                    
                    # Criar registro de folga
                    registro_folga = RegistroPonto(
                        funcionario_id=funcionario.id,
                        data=data_atual,
                        tipo_registro=tipo_folga,
                        horas_trabalhadas=0,
                        observacoes=f'Folga automática Vale Verde - {data_atual.strftime("%d/%m/%Y")}'
                    )
                    
                    db.session.add(registro_folga)
                    registros_criados += 1
            
            data_atual += timedelta(days=1)
    
    # Criar alguns registros de férias de exemplo
    print(f"\nCriando registros de férias de exemplo...")
    
    # Pegar primeiro funcionário para criar férias em julho
    if funcionarios_vale_verde:
        funcionario_ferias = funcionarios_vale_verde[0]
        
        # Período de férias: 15-29 de julho
        data_ferias_inicio = date(2025, 7, 15)
        data_ferias_fim = date(2025, 7, 29)
        
        data_atual = data_ferias_inicio
        while data_atual <= data_ferias_fim:
            # Verificar se não existe registro
            registro_existente = RegistroPonto.query.filter(
                RegistroPonto.funcionario_id == funcionario_ferias.id,
                RegistroPonto.data == data_atual
            ).first()
            
            if not registro_existente:
                registro_ferias = RegistroPonto(
                    funcionario_id=funcionario_ferias.id,
                    data=data_atual,
                    tipo_registro='ferias',
                    horas_trabalhadas=0,
                    observacoes=f'Férias - período 15-29/07/2025'
                )
                
                db.session.add(registro_ferias)
                registros_ferias += 1
            
            data_atual += timedelta(days=1)
    
    # Commit das alterações
    db.session.commit()
    
    print(f"\n✅ RESULTADOS:")
    print(f"   • Registros de folga criados: {registros_criados}")
    print(f"   • Registros de férias criados: {registros_ferias}")
    print(f"   • Funcionários processados: {len(funcionarios_vale_verde)}")
    
    return registros_criados, registros_ferias

def validar_novos_tipos():
    """Valida se os novos tipos estão sendo utilizados"""
    
    print("\nVALIDANDO NOVOS TIPOS DE LANÇAMENTO")
    print("=" * 50)
    
    tipos_novos = ['sabado_folga', 'domingo_folga', 'ferias']
    
    for tipo in tipos_novos:
        count = db.session.query(RegistroPonto).filter_by(tipo_registro=tipo).count()
        print(f"  • {tipo}: {count} registros")
    
    # Estatísticas gerais
    total_registros = db.session.query(RegistroPonto).count()
    print(f"\nTotal geral de registros: {total_registros}")
    
    # Tipos únicos no sistema
    tipos_sistema = db.session.query(RegistroPonto.tipo_registro.distinct()).all()
    tipos_sistema = [t[0] for t in tipos_sistema if t[0]]
    
    print(f"Tipos únicos no sistema: {len(tipos_sistema)}")
    for tipo in sorted(tipos_sistema):
        count = db.session.query(RegistroPonto).filter_by(tipo_registro=tipo).count()
        print(f"  • {tipo}: {count}")

def atualizar_interface_tipos():
    """Cria interface atualizada com os novos tipos"""
    
    interface_html = """
    <!-- TIPOS DE LANÇAMENTO v8.1 - INTERFACE ATUALIZADA -->
    <div class="row mb-3">
        <div class="col-md-6">
            <label class="form-label">Tipo de Registro *</label>
            <select class="form-select" name="tipo_registro" required>
                <option value="">Selecione o tipo...</option>
                
                <optgroup label="📋 TRABALHO">
                    <option value="trabalho_normal">Trabalho Normal</option>
                    <option value="sabado_trabalhado">Sábado Trabalhado (+50%)</option>
                    <option value="domingo_trabalhado">Domingo Trabalhado (+100%)</option>
                    <option value="feriado_trabalhado">Feriado Trabalhado (+100%)</option>
                </optgroup>
                
                <optgroup label="⚠️ AUSÊNCIAS">
                    <option value="falta">Falta (desconta salário)</option>
                    <option value="falta_justificada">Falta Justificada</option>
                    <option value="ferias">Férias (+33%)</option>
                </optgroup>
                
                <optgroup label="🏠 FOLGAS">
                    <option value="sabado_folga">Sábado - Folga</option>
                    <option value="domingo_folga">Domingo - Folga</option>
                    <option value="feriado_folga">Feriado - Folga</option>
                </optgroup>
            </select>
        </div>
    </div>
    
    <script>
    // JavaScript para mostrar/ocultar campos baseado no tipo
    document.addEventListener('DOMContentLoaded', function() {
        const tipoSelect = document.querySelector('select[name="tipo_registro"]');
        const horasField = document.querySelector('input[name="horas_trabalhadas"]');
        
        tipoSelect.addEventListener('change', function() {
            const tiposSemHoras = ['falta', 'sabado_folga', 'domingo_folga', 'feriado_folga'];
            
            if (tiposSemHoras.includes(this.value)) {
                horasField.value = '0';
                horasField.readOnly = true;
                horasField.style.backgroundColor = '#f8f9fa';
            } else {
                horasField.readOnly = false;
                horasField.style.backgroundColor = '';
                
                // Definir valor padrão baseado no tipo
                if (this.value === 'trabalho_normal') {
                    horasField.value = '8.0';
                } else if (this.value.includes('trabalhado')) {
                    horasField.value = '8.0';
                }
            }
        });
    });
    </script>
    """
    
    with open('interface_tipos_v8_1.html', 'w', encoding='utf-8') as f:
        f.write(interface_html)
    
    print("✅ Interface atualizada salva em: interface_tipos_v8_1.html")

if __name__ == "__main__":
    with app.app_context():
        print("ADICIONANDO TIPOS DE FOLGA E FÉRIAS - SIGE v8.1")
        print("=" * 80)
        
        # Criar registros de folga para Vale Verde
        folgas_criadas, ferias_criadas = criar_registros_folga_vale_verde()
        
        # Validar novos tipos
        validar_novos_tipos()
        
        # Criar interface atualizada
        atualizar_interface_tipos()
        
        print("\n" + "=" * 80)
        print("CONCLUSÃO - TIPOS ADICIONADOS COM SUCESSO")
        print("=" * 80)
        print(f"✅ Registros de folga: {folgas_criadas}")
        print(f"✅ Registros de férias: {ferias_criadas}")
        print("✅ Interface atualizada")
        print("✅ Sistema pronto para usar todos os 10 tipos v8.1")