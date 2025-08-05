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
✅ João Silva Santos 31/07: 0.95h extras - 50%
✅ Ana Paula Rodrigues 29/07: 1.0h extras, 0.3h atrasos
✅ HOTFIX APLICADO COM SUCESSO!
```

## 🔍 VALIDAÇÃO

Após executar, verifique na interface:
- João Silva Santos 31/07/2025: deve mostrar **"0.95h - 50%"**
- Ana Paula Rodrigues 29/07/2025: deve mostrar **"1.0h - 50%"** e **18min atraso**

## 📊 LÓGICA APLICADA

**Horário padrão**: 07:12-17:00 (todos funcionários)

**João Silva Santos 31/07:**
- Real: 07:05-17:50
- Antecipação: 07:12 - 07:05 = 7min
- Prolongamento: 17:50 - 17:00 = 50min
- **Total extras: 57min = 0.95h**

**Ana Paula Rodrigues 29/07:**
- Real: 07:30-18:00
- Atraso: 07:30 - 07:12 = 18min = 0.3h
- Prolongamento: 18:00 - 17:00 = 60min = 1.0h
- **Resultado: 1.0h extras + 0.3h atrasos**

## ⚠️ BACKUP
Recomenda-se fazer backup do banco antes de executar (opcional, pois a correção é segura).