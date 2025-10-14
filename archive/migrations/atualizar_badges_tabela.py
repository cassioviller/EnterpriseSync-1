#!/usr/bin/env python3
"""
ATUALIZAR BADGES DA TABELA DE CONTROLE DE PONTO
Atualiza as badges para incluir todos os tipos v8.1
"""

import os

def verificar_badges_atualizadas():
    """Verifica se as badges foram atualizadas corretamente"""
    
    template_path = 'templates/controle_ponto.html'
    
    if not os.path.exists(template_path):
        print("❌ Template não encontrado")
        return False
    
    with open(template_path, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    badges_esperadas = [
        'sabado_trabalhado',
        'domingo_trabalhado',
        'feriado_trabalhado',
        'sabado_folga',
        'domingo_folga',
        'feriado_folga',
        'ferias'
    ]
    
    print("VERIFICANDO BADGES NA TABELA")
    print("=" * 50)
    
    badges_encontradas = []
    for badge in badges_esperadas:
        if f"registro.tipo_registro == '{badge}'" in conteudo:
            badges_encontradas.append(badge)
    
    porcentagem = (len(badges_encontradas) / len(badges_esperadas)) * 100
    status = "✅" if porcentagem >= 80 else "❌"
    
    print(f"{status} Badges encontradas: {len(badges_encontradas)}/{len(badges_esperadas)} ({porcentagem:.0f}%)")
    
    if len(badges_encontradas) < len(badges_esperadas):
        faltando = set(badges_esperadas) - set(badges_encontradas)
        print(f"Faltando: {', '.join(faltando)}")
    else:
        print("✅ Todas as badges estão implementadas!")
    
    return len(badges_encontradas) == len(badges_esperadas)

def criar_exemplo_badges():
    """Cria exemplo das badges para os novos tipos"""
    
    badges_exemplo = """
<!-- BADGES PARA TIPOS v8.1 -->

<!-- COLUNA TIPO -->
{% if registro.tipo_registro == 'trabalho_normal' %}
    <span class="badge bg-success">👷 Trabalho Normal</span>
{% elif registro.tipo_registro == 'sabado_trabalhado' %}
    <span class="badge bg-warning">📅 Sábado Trabalhado</span>
{% elif registro.tipo_registro == 'domingo_trabalhado' %}
    <span class="badge bg-danger">📅 Domingo Trabalhado</span>
{% elif registro.tipo_registro == 'feriado_trabalhado' %}
    <span class="badge bg-info">🎉 Feriado Trabalhado</span>
{% elif registro.tipo_registro == 'falta' %}
    <span class="badge bg-danger">❌ Falta</span>
{% elif registro.tipo_registro == 'falta_justificada' %}
    <span class="badge bg-primary">⚕️ Falta Justificada</span>
{% elif registro.tipo_registro == 'ferias' %}
    <span class="badge bg-success">🏖️ Férias</span>
{% elif registro.tipo_registro == 'sabado_folga' %}
    <span class="badge bg-light text-dark">📅 Sábado - Folga</span>
{% elif registro.tipo_registro == 'domingo_folga' %}
    <span class="badge bg-light text-dark">📅 Domingo - Folga</span>
{% elif registro.tipo_registro == 'feriado_folga' %}
    <span class="badge bg-secondary">🎉 Feriado - Folga</span>
{% endif %}

<!-- COLUNA DATA (pequenas badges) -->
{% if registro.tipo_registro == 'sabado_trabalhado' or registro.tipo_registro == 'sabado_folga' %}
    <span class="badge bg-success ms-1">SÁBADO</span>
{% elif registro.tipo_registro == 'domingo_trabalhado' or registro.tipo_registro == 'domingo_folga' %}
    <span class="badge bg-warning ms-1">DOMINGO</span>
{% elif registro.tipo_registro == 'feriado_trabalhado' or registro.tipo_registro == 'feriado_folga' %}
    <span class="badge bg-info ms-1">FERIADO</span>
{% elif registro.tipo_registro == 'ferias' %}
    <span class="badge bg-success ms-1">FÉRIAS</span>
{% elif registro.tipo_registro == 'falta_justificada' %}
    <span class="badge bg-primary ms-1">JUSTIFICADA</span>
{% elif registro.tipo_registro == 'falta' %}
    <span class="badge bg-danger ms-1">FALTA</span>
{% endif %}
"""
    
    with open('badges_exemplo_v8_1.html', 'w', encoding='utf-8') as f:
        f.write(badges_exemplo)
    
    print("✅ Exemplo de badges criado: badges_exemplo_v8_1.html")

if __name__ == "__main__":
    print("VERIFICANDO BADGES DA TABELA v8.1")
    print("=" * 60)
    
    # Verificar estado atual
    badges_ok = verificar_badges_atualizadas()
    
    # Criar exemplo
    criar_exemplo_badges()
    
    print("\n" + "=" * 60)
    if badges_ok:
        print("✅ TUDO CORRETO: Badges implementadas!")
    else:
        print("⚠️  AÇÃO NECESSÁRIA: Algumas badges ainda precisam ser implementadas")
    
    print("✅ Exemplo de badges criado para referência")