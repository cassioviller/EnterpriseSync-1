# 🔍 COMO CAPTURAR LOGS DE ERRO EM PRODUÇÃO - SIGE

## 📋 INSTRUÇÕES PARA O USUÁRIO

Quando aparecer o **Erro 500** em produção, agora você terá acesso a **logs detalhados** para enviar para análise.

### 🚀 PASSOS PARA CAPTURAR O ERRO:

#### 1. **Acesse a URL que está dando erro**
```
https://sige.cassioviller.tech/funcionarios
```

#### 2. **Capturar Screenshot da Página de Erro**
A nova página de erro mostrará:
- ✅ **Detalhes Técnicos do Erro** (seção expandida)
- ✅ **URL que causou o erro**
- ✅ **Timestamp exato**
- ✅ **Traceback completo do Python**
- ✅ **Headers da requisição**
- ✅ **Parâmetros enviados**

#### 3. **Fazer Screenshots de:**
- 📸 **Tela inteira** da página de erro
- 📸 **Seção "Detalhes Técnicos"** com scroll até o final
- 📸 **Console do navegador** (F12 → Console)

### 🛠️ COMO ACESSAR CONSOLE DO NAVEGADOR:

1. **Pressione F12** (ou clique direito → Inspecionar)
2. **Vá na aba "Console"**
3. **Screenshot dos erros JavaScript** (se houver)
4. **Vá na aba "Network"**
5. **Recarregue a página (F5)**
6. **Screenshot das requisições vermelhas** (se houver)

### 📊 O QUE OS LOGS VÃO MOSTRAR:

```
ERRO: unsupported format string passed to Undefined.__format__

URL: https://sige.cassioviller.tech/funcionarios
MÉTODO: GET
TIMESTAMP: 15/08/2025 11:35:14
USER AGENT: Mozilla/5.0...

TRACEBACK COMPLETO:
Traceback (most recent call last):
  File "/app/views.py", line 245, in funcionarios
    return render_template('funcionarios.html', ...)
  File "/usr/local/lib/python3.11/site-packages/jinja2/environment.py", line 1301, in render
    return self.environment.handle_exception()
jinja2.exceptions.UndefinedError: 'dict object' has no attribute '__format__'

HEADERS DA REQUISIÇÃO:
{'Host': 'sige.cassioviller.tech', 'User-Agent': '...', ...}

ARGUMENTOS DA REQUISIÇÃO:
{'data_inicio': '2024-07-01', 'data_fim': '2024-07-31'}
```

### 🎯 **ROTAS PARA TESTAR EM PRODUÇÃO:**

#### ✅ **Rotas Seguras (devem funcionar):**
```
https://sige.cassioviller.tech/prod/safe-dashboard
https://sige.cassioviller.tech/prod/safe-funcionarios
https://sige.cassioviller.tech/prod/debug-info
```

#### ⚠️ **Rotas Normais (podem ter erro):**
```
https://sige.cassioviller.tech/dashboard
https://sige.cassioviller.tech/funcionarios
```

### 📝 **INFORMAÇÕES PARA ENVIAR:**

Quando capturar os erros, envie:

1. **Screenshots da página de erro completa**
2. **Screenshot dos "Detalhes Técnicos"** 
3. **Screenshot do console do navegador**
4. **URL exata que estava acessando**
5. **O que estava tentando fazer** (ex: "acessar lista de funcionários")

### 🚀 **TESTE RÁPIDO:**

Para verificar se o sistema está funcionando, acesse:
```
https://sige.cassioviller.tech/prod/debug-info
```

**Deve retornar:**
```json
{
  "admin_id_detectado": 2,
  "funcionarios_admin": 27,
  "status": "OK",
  "total_funcionarios_sistema": 27
}
```

### 📞 **SUPORTE:**

Com essas informações detalhadas, será possível:
- ✅ Identificar **exatamente** onde está o erro
- ✅ Corrigir o **template específico** que está falhando
- ✅ Implementar **fix direcionado** para produção
- ✅ **Deploy rápido** da correção

**Agora o diagnóstico será preciso e a correção será imediata!**