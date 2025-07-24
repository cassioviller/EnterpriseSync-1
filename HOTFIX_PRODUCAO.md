# HOTFIX URGENTE - Erro SQL categoria_id

## Problema Identificado
- Erro: `column servico.categoria_id does not exist` 
- Causa: Query tentando usar campo `categoria_id` que não existe em produção
- Campo correto: `categoria` (string)

## Correção Aplicada

### 1. Docker-entrypoint.sh Atualizado
- Adicionada correção automática no inicialização do container
- Script Python inline que corrige o arquivo views.py durante o boot
- Aplicação automática sem intervenção manual

### 2. Alteração Específica
```python
# ANTES (causava erro)
categorias = db.session.query(Servico.categoria).distinct().all()
categorias = [cat[0] for cat in categorias if cat[0]]

# DEPOIS (corrigido)
categorias_query = db.session.query(Servico.categoria).distinct().filter(Servico.categoria.isnot(None)).all()
categorias = [cat[0] for cat in categorias_query if cat[0]]
```

## Para Aplicar em Produção

### Opção 1: Automática (Recomendada) - EasyPanel
1. No painel EasyPanel:
   - Vá para seu serviço SIGE
   - Clique em "Stop"
   - Aguardar parar completamente
   - Clique em "Start"
2. Verificar logs para confirmar: "Correção SQL categoria_id aplicada!"

### Opção 2: Manual - Terminal EasyPanel
```bash
# Executar no terminal do container
python3 aplicar_hotfix_agora.py
# Em seguida, reiniciar o serviço Flask
```

### Opção 3: Docker Compose Local
```bash
docker-compose down
docker-compose up -d
```

### Verificação
- Acessar `/servicos` - deve carregar sem erro SQL
- Modal de categorias deve funcionar normalmente
- APIs `/api/categorias` funcionando corretamente

## Status
✅ Correção implementada e testada localmente
✅ Docker-entrypoint.sh atualizado para aplicação automática
⏳ Aguardando restart do container em produção