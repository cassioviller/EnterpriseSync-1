# HOTFIX PRODUÇÃO - Correção Horas Extras

## 🚨 PROBLEMA IDENTIFICADO
- Registros de ponto com cálculo incorreto de horas extras
- João Silva Santos 31/07/2025 deveria mostrar **0.95h extras** (não 1.8h)
- Ana Paula Rodrigues 29/07/2025 deveria mostrar **1.0h extras + 0.3h atrasos**

## 🔧 SOLUÇÃO
Execute o arquivo `HOTFIX_HORAS_EXTRAS_PRODUCAO.py` no ambiente de produção.

## 📋 PASSOS PARA APLICAR

### 1. Upload do arquivo
```bash
# Copie o arquivo HOTFIX_HORAS_EXTRAS_PRODUCAO.py para o servidor de produção
```

### 2. Execute a correção
```bash
cd /caminho/do/projeto/producao
python HOTFIX_HORAS_EXTRAS_PRODUCAO.py
```

### 3. Reinicie o servidor
```bash
# Reinicie o servidor web para limpar cache
sudo systemctl restart gunicorn  # ou seu comando de restart
```

## ✅ RESULTADO ESPERADO

O script deve mostrar:
```
📊 ESTATÍSTICAS:
   Total de registros processados: XXX
   Registros corrigidos: XXX
   Taxa de correção: XX.X%
✅ HOTFIX APLICADO COM SUCESSO!
```

## 🔍 VALIDAÇÃO

Após executar, verifique registros na interface:
- Todos os cálculos de horas extras devem estar baseados no horário individual
- Atrasos calculados por entrada tardia + saída antecipada
- Horas extras calculadas por entrada antecipada + saída posterior

## 📊 LÓGICA APLICADA

**Horário padrão**: 07:12-17:00 (todos funcionários)

**Fórmulas de cálculo:**
- **Atrasos**: entrada tardia + saída antecipada (em minutos)
- **Horas extras**: entrada antecipada + saída posterior (em minutos)
- **Percentual**: 50% para qualquer hora extra > 0

**Exemplo prático:**
- Horário real: 07:05-17:50 vs Padrão: 07:12-17:00
- Extras: 7min (antecipação) + 50min (prolongamento) = 57min = 0.95h
- Resultado: 0.95h extras com 50% adicional

## ⚠️ BACKUP
Recomenda-se fazer backup do banco antes de executar (opcional, pois a correção é segura).