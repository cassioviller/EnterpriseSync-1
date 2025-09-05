#!/usr/bin/env python3
"""
CORREÇÃO CRÍTICA RDO PRODUÇÃO - APLICAÇÃO DIRETA
Aplica os logs e correções necessárias diretamente no views.py
"""
import os
import re

def aplicar_logs_rdo_producao():
    """Aplica logs específicos para capturar erro de subatividades em produção"""
    
    views_path = '/app/views.py'
    
def corrigir_svg_base():
    """Corrige o problema do SVG corrompido no template base"""
    
    base_path = '/app/templates/base.html'
    
    if not os.path.exists(base_path):
        print(f"❌ Arquivo {base_path} não encontrado")
        return False
    
    print("🔧 Corrigindo SVG corrompido no template base...")
    
    with open(base_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Corrigir o SVG problemático
    old_svg = r'const svg = `data:image/svg\+xml;base64,\$\{btoa\(`'
    new_svg = 'const svg = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(`'
    
    if re.search(old_svg, content):
        content = re.sub(old_svg, new_svg, content)
        
        try:
            with open(base_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ SVG corrompido corrigido no template base")
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar base.html: {e}")
            return False
    else:
        print("ℹ️ SVG já estava correto")
        return True
    
    if not os.path.exists(views_path):
        print(f"❌ Arquivo {views_path} não encontrado")
        return False
    
    print("🔧 Aplicando correções de logs RDO para produção...")
    
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Correção 1: Adicionar logs no início do processamento de subatividades
    old_pattern = r'print\("DEBUG CORRIGIDO: Processando subatividades do formulário\.\.\."\)'
    new_code = '''print("❌ [RDO_SAVE] INICIO_PROCESSAMENTO_SUBATIVIDADES")
        print(f"❌ [RDO_SAVE] ADMIN_ID_USADO: {admin_id_correto}")
        print(f"❌ [RDO_SAVE] TOTAL_CAMPOS_FORM: {len(request.form)}")
        print("❌ [RDO_SAVE] TODOS_CAMPOS_FORM:")'''
    
    if re.search(old_pattern, content):
        content = re.sub(old_pattern, new_code, content)
        print("✅ Logs de início aplicados")
    
    # Correção 2: Adicionar validação de erro quando não há subatividades
    old_validation = r'print\(f"✅ TOTAL SUBATIVIDADES PROCESSADAS: \{subatividades_processadas\}"\)'
    new_validation = '''print(f"❌ [RDO_SAVE] TOTAL_SUBATIVIDADES_PROCESSADAS: {subatividades_processadas}")
        
        # VALIDAÇÃO ESPECÍFICA PARA PRODUÇÃO
        if subatividades_processadas == 0:
            print("❌ [RDO_SAVE] ERRO_VALIDACAO_PRODUCAO:")
            print(f"   - Nenhuma subatividade processada")
            print(f"   - Admin_ID: {admin_id_correto}")
            flash('Erro de validação: Nenhuma subatividade encontrada no formulário', 'error')
            return redirect(url_for('main.rdo_novo_unificado'))'''
    
    if re.search(old_validation, content):
        content = re.sub(old_validation, new_validation, content)
        print("✅ Validação de erro aplicada")
    
    # Salvar arquivo corrigido
    try:
        with open(views_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Arquivo views.py atualizado com logs de produção")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar views.py: {e}")
        return False

if __name__ == "__main__":
    print("🎯 INICIANDO CORREÇÃO RDO + SVG PRODUÇÃO")
    
    # Corrigir SVG primeiro
    svg_ok = corrigir_svg_base()
    
    # Aplicar logs RDO
    rdo_ok = aplicar_logs_rdo_producao()
    
    if svg_ok and rdo_ok:
        print("✅ TODAS AS CORREÇÕES APLICADAS COM SUCESSO!")
    else:
        print("❌ FALHA EM ALGUMAS CORREÇÕES")
        exit(1)