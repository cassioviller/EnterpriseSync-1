from app import app, db
from models import ConfiguracaoEmpresa
from flask import render_template_string

@app.route('/teste-header')
def teste_header():
    """Teste simples do header PDF"""
    config = ConfiguracaoEmpresa.query.filter_by(admin_id=10).first()
    
    teste_html = """
    <h1>Teste do Header PDF</h1>
    
    {% if config and config.header_pdf_base64 %}
        <h2>✅ Header PDF encontrado!</h2>
        <p><strong>Tamanho:</strong> {{ config.header_pdf_base64|length }} caracteres</p>
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
            <h3>Preview do Header:</h3>
            <img src="data:image/jpeg;base64,{{ config.header_pdf_base64 }}" 
                 alt="Header PDF" 
                 style="max-width: 100%; height: auto; border: 1px solid #ddd;">
        </div>
    {% else %}
        <h2>❌ Header PDF não encontrado</h2>
        <p>Configuração da empresa: {{ config.nome_empresa if config else 'Não encontrada' }}</p>
    {% endif %}
    
    <hr>
    <h3>Template PDF com Header:</h3>
    <div style="border: 2px solid #000; padding: 20px; background: white; width: 210mm; margin: 20px auto;">
        {% if config and config.header_pdf_base64 %}
            <div style="width: 100%; height: 120px; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; overflow: hidden; background: #f5f5f5;">
                <img src="data:image/jpeg;base64,{{ config.header_pdf_base64 }}" 
                     alt="Header Personalizado" 
                     style="max-width: 100%; max-height: 120px; object-fit: contain;">
            </div>
            <p><strong>✅ Header personalizado carregado!</strong></p>
        {% else %}
            <div style="background: #52c41a; color: white; padding: 20px; display: flex; align-items: center;">
                <div>
                    <h1 style="margin: 0; color: white;">{{ config.nome_empresa if config else 'Estruturas do Vale' }}</h1>
                    <p style="margin: 5px 0 0 0; color: white;">ESTRUTURAS METÁLICAS</p>
                </div>
            </div>
            <p><strong>❌ Usando header padrão</strong></p>
        {% endif %}
        
        <h2>Conteúdo da Proposta</h2>
        <p>Este é um teste de como o header apareceria no PDF final...</p>
    </div>
    """
    
    return render_template_string(teste_html, config=config)

if __name__ == '__main__':
    with app.app_context():
        result = teste_header()
        print(result)