# SIGE — Sistema Integrado de Gestão Empresarial

Sistema de gestão para construtoras em Flask + PostgreSQL. Inclui módulos de CRM, orçamento, cronograma, fluxo de caixa, almoxarifado, RDO, equipe, compras e mais.

## Como rodar

O workflow **Start application** inicia o servidor via gunicorn na porta 5000:

```
.pythonlibs/bin/gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

## Variáveis de ambiente necessárias

| Variável | Descrição |
|---|---|
| `SESSION_SECRET` | Chave secreta da sessão Flask (já configurada) |
| `DATABASE_URL` | URL do PostgreSQL (ex: `postgresql://user:pass@host/db`) |
| `SIGE_ENV` | Ambiente: `development` ou `production` (opcional, usa heurística sem isso) |

## Stack

- **Backend**: Python / Flask
- **ORM**: Flask-SQLAlchemy + Flask-Migrate
- **Banco**: PostgreSQL (psycopg2)
- **Servidor**: Gunicorn
- **Entrada**: `main.py` → importa `app` de `app.py`

## User preferences

- Language: Portuguese (pt-BR)
