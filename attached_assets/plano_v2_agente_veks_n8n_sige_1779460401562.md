# Plano V2 — Agente Veks n8n integrado ao CRM SIGE

PLANO V2 - AGENTE VEKS N8N INTEGRADO AO CRM SIGE
Formato: TXT / Markdown simples
Observacao: revisar e testar no ambiente do SIGE e do n8n antes de implementar em producao.

# PLANO V2 DE IMPLEMENTACAO
Agente de Atendimento Veks Engenharia no n8n
Integrado ao CRM nativo do SIGE
Light Steel Frame | Atendimento consultivo | Qualificacao comercial | Handoff humano | Agendamento tecnico

| Versao melhorada: este plano substitui a ideia inicial baseada em Notion por uma arquitetura integrada ao CRM do SIGE, com API interna, controle de estado, logs, seguranca, follow-up e workflows n8n modulares. |
| --- |


| Item | Definição |
| --- | --- |
| Cliente / Projeto | Veks Engenharia - agente comercial para atendimento via WhatsApp. |
| Sistema destino | SIGE - CRM nativo como fonte oficial dos leads, historico, status, proximas acoes e handoff. |
| Orquestrador | n8n, usando nodes nativos sempre que possivel e HTTP Request para APIs externas/internas. |
| Decisao principal | Nao reaproveitar o workflow antigo como esta. Usar a base como referencia e criar arquitetura V2 modular. |
| Entrega deste documento | Plano de implementacao no sistema + esboco de workflow n8n + checklist de testes e riscos. |


# Sumario executivo

| Resumo curto: o novo agente deve ser tratado como produto integrado ao SIGE, nao como automacao isolada. O CRM do SIGE deve receber leads por API, o n8n deve conduzir a conversa e a IA deve operar com regras claras, estado incremental e handoff humano. |
| --- |


A base da Veks define corretamente o tom consultivo, os campos de qualificacao, as personas, objeções e regras de handoff.
O plano anterior ainda estava muito preso ao fluxo antigo. A versao V2 muda a arquitetura: SIGE vira sistema de registro oficial e Notion sai do fluxo.
A integracao deve ser feita por uma API interna do SIGE, nao por escrita direta no banco nem por automacao via tela logada.
O workflow n8n deve ser dividido em blocos menores: entrada WhatsApp, atendimento IA, upsert no CRM, handoff, agendamento, follow-up e RAG.
A primeira entrega deve ser um MVP seguro: texto no WhatsApp + agente + upsert no CRM + registro de historico + handoff. Audio, imagem, agenda e follow-up entram em fases seguintes.

# 1. O que mudou em relacao ao plano anterior

| Ponto | Antes | Plano V2 recomendado |
| --- | --- | --- |
| Destino do lead | Notion ou planilha como CRM externo. | CRM nativo do SIGE como fonte oficial. |
| Workflow | Um fluxo grande, com atendimento, RAG, agenda, CRM e follow-up juntos. | Workflows menores e especializados, ligados por APIs/eventos. |
| WhatsApp | Dependente do formato antigo da API usada no fluxo de marco. | Camada adaptadora para funcionar com Evolution API, Cloud API, Z-API ou outro provedor. |
| Persistencia | Memoria em Redis/Postgres e CRM externo. | Estado conversacional + historico + lead no SIGE. |
| IA | Agente decide muita coisa sozinho. | Agente conversa, qualifica e sugere; SIGE valida status, dados e regras. |
| Handoff | Regra no prompt. | Regra no prompt + campo estruturado + alerta interno + status no CRM. |
| Producao | Risco de ativar nodes antigos, pinData e credenciais antigas. | Implementacao limpa, sem dados sensiveis no JSON e com tokens por credencial/variavel de ambiente. |


# 2. Premissas e decisoes de arquitetura

| Decisao | Motivo | Impacto pratico |
| --- | --- | --- |
| SIGE como fonte oficial do CRM | Evita duplicidade de bases e permite que o time comercial trabalhe no Kanban do sistema. | Todo lead, status, historico e proxima acao devem ser gravados no SIGE. |
| n8n como orquestrador | Facilita integracao com WhatsApp, IA, RAG, agenda, alertas e logs. | O n8n nao deve guardar regra comercial permanente que pertence ao SIGE. |
| API interna no SIGE | As rotas atuais do CRM sao de tela e login. Automacao precisa de endpoint JSON seguro. | Criar blueprint de integracao com token, validacao e idempotencia. |
| Camada adaptadora de WhatsApp | A API do WhatsApp pode mudar novamente. | Normalizar todo provedor para um payload interno padrao. |
| Estado incremental do lead | Evita perguntar novamente o que o cliente ja respondeu. | Manter JSON de qualificacao atualizado no SIGE/n8n. |
| Handoff humano formalizado | A base da Veks exige handoff em casos tecnicos/comerciais sensiveis. | Criar status/campo no lead e notificar responsavel. |
| MVP por fases | Reduz risco de um workflow grande quebrar. | Primeiro texto + CRM; depois midia, RAG, agenda e follow-up. |


# 3. Base tecnica observada no SIGE
O CRM do SIGE ja possui rotas para Kanban, lista, novo lead, edicao, mudanca de status, gerar proposta e criar obra.
A criacao/edicao atual do lead valida campos como nome, contato, e-mail, origem, tipo de obra, tipo de material, localizacao, demanda, valor da proposta, observacao e status.
O CRM opera com isolamento por tenant/admin_id e precisa preservar esse padrao na integracao externa.
O app.py ja registra blueprints de modulos de forma modular, entao o ideal e criar um blueprint novo para API de integracoes do CRM.
O app usa CSRFProtect para telas. Endpoints de API para n8n precisam ser tratados com autenticacao por token e isencao controlada de CSRF, sem expor o token no codigo.

# 4. Arquitetura alvo

| WhatsApp Provider   -> Webhook n8n   -> Normalizador de mensagem   -> Estado da conversa / historico   -> RAG Veks + regras comerciais   -> Agente IA consultivo   -> Validador de JSON estruturado   -> API interna SIGE CRM   -> Kanban / lista / historico / handoff   -> Resposta WhatsApp   -> Logs e monitoramento |
| --- |


## 4.1 Separacao entre responsabilidades

| Camada | Responsabilidade | Nao deve fazer |
| --- | --- | --- |
| WhatsApp provider | Entregar eventos de mensagens e enviar respostas. | Guardar regra comercial ou decidir status do lead. |
| n8n | Orquestrar recebimento, IA, RAG, validacao, chamadas API, agenda e follow-up. | Virar banco oficial do CRM ou conter regra sensivel sem validacao. |
| Agente IA | Conversar, qualificar, educar, extrair dados e sugerir proximo passo. | Prometer preco, prazo, garantia ou viabilidade sem avaliacao humana. |
| SIGE API | Validar dados, criar/atualizar lead, registrar historico, status, handoff e agenda. | Depender de automacao visual da tela do CRM. |
| CRM SIGE | Ser a interface operacional do time comercial. | Depender do Notion para visualizar o funil. |
| Equipe humana | Assumir casos quentes, tecnicos, projeto pronto, reuniao e fechamento. | Receber alerta sem contexto do atendimento. |


# 5. Melhorias recomendadas no modelo de dados do CRM

| O sistema pode comecar usando campos existentes do Lead e LeadHistorico. Porem, para uma integracao profissional e rastreavel, recomendo adicionar alguns campos/tabelas. Isso reduz duplicidade, melhora follow-up e permite auditoria. |
| --- |


## 5.1 Campos novos sugeridos em Lead

| Campo sugerido | Tipo | Uso |
| --- | --- | --- |
| external_id | String indexado | Identificador do lead vindo do canal externo. Ex.: whatsapp_5512999999999. |
| canal_origem | String | WhatsApp, Site, Landing Page, Instagram, Indicacao. |
| origem_integracao | String | Ex.: agente_veks_n8n. |
| whatsapp_phone | String indexado | Telefone normalizado somente com digitos. |
| whatsapp_jid | String | Identificador tecnico do contato, se existir no provedor. |
| ultimo_message_id | String indexado | Controle de idempotencia para nao processar mensagem repetida. |
| tipo_atendimento | String/enum | orcamento, duvida_tecnica, parceria, pos_venda, fornecedor, outro. |
| perfil_lead | String/enum | cliente_final, investidor, arquiteto, engenheiro, construtora, comercial, fora_escopo. |
| temperatura | String/enum | quente, morno, frio, parceria, fora_escopo. |
| resumo_atendimento | Text | Resumo vivo da conversa para o vendedor entender rapidamente. |
| ultima_interacao_em | DateTime | Base para follow-up e priorizacao. |
| proxima_acao | String/enum | orcamento, reuniao, envio_material, humano, followup, aguardar_projeto. |
| necessita_humano | Boolean | Marca handoff humano. |
| motivo_handoff | Text | Explica por que a IA transferiu o atendimento. |
| possui_terreno | String/enum | sim, nao, em_negociacao, nao_informado. |
| possui_projeto | String/enum | sim, nao, em_desenvolvimento, nao_informado. |
| metragem_aproximada | Numeric/String | Pode ser numero ou texto quando o cliente nao souber ao certo. |
| prazo_desejado | String | Texto livre, sem promessa de prazo. |
| dor_principal | String/Text | prazo, custo, seguranca, previsibilidade, sustentabilidade, acabamento, outro. |


## 5.2 Tabela nova recomendada: LeadMensagem ou LeadInteracao

| Campo | Uso |
| --- | --- |
| id | Identificador interno. |
| lead_id | FK para Lead. |
| admin_id | Isolamento por tenant. |
| canal | WhatsApp, e-mail, site etc. |
| direcao | entrada ou saida. |
| message_id | ID externo para idempotencia. |
| telefone | Telefone normalizado. |
| tipo_mensagem | text, audio, image, document, video, unknown. |
| conteudo_texto | Texto recebido/enviado ou transcricao. |
| media_url | URL/identificador de midia, sem expor dados sensiveis em logs. |
| payload_resumido | JSON reduzido e seguro para auditoria. |
| criado_em | Data/hora da interacao. |


## 5.3 Por que nao gravar direto no banco via n8n
Gravacao direta pula regras de tenant/admin_id, validacoes e historico.
Aumenta risco de lead duplicado ou status invalido.
Dificulta alterar regras depois, porque a regra fica espalhada no n8n.
Complica seguranca: o n8n teria acesso direto ao banco de producao.

# 6. API interna do SIGE para integracao com n8n

## 6.1 Blueprint sugerido

| Arquivo: api_crm_integracoes.py Blueprint: api_crm_integracoes_bp Prefixo: /api/integracoes/crm Registro em app.py: app.register_blueprint(api_crm_integracoes_bp) |
| --- |


## 6.2 Endpoints recomendados

| Endpoint | Metodo | Funcao | Prioridade |
| --- | --- | --- | --- |
| /api/integracoes/crm/health | GET | Validar se a API esta online e autenticacao funciona. | MVP |
| /api/integracoes/crm/meta/opcoes | GET | Retornar listas mestre: origens, tipos de obra, materiais, responsaveis, status validos. | MVP |
| /api/integracoes/crm/leads/upsert | POST | Criar ou atualizar lead por telefone, e-mail, external_id ou whatsapp_jid. | MVP |
| /api/integracoes/crm/leads/{id}/mensagens | POST | Registrar mensagem, transcricao, resumo ou resposta enviada. | MVP |
| /api/integracoes/crm/leads/{id}/handoff | POST | Marcar que o lead precisa de atendimento humano e notificar responsavel. | MVP+ |
| /api/integracoes/crm/leads/{id}/status | POST/PATCH | Alterar status de forma controlada. | MVP+ |
| /api/integracoes/crm/leads/{id}/agendamentos | POST | Registrar reuniao/visita vinculada ao lead. | Fase 2 |
| /api/integracoes/crm/followups/candidatos | GET | Listar leads parados que podem receber follow-up. | Fase 3 |
| /api/integracoes/crm/followups/registrar | POST | Registrar follow-up enviado e evitar repeticao. | Fase 3 |


## 6.3 Autenticacao e seguranca da API
Usar Authorization: Bearer configurado no n8n como credencial segura, nunca escrito em node, JSON, prompt ou documento operacional.
Token deve ser lido no SIGE por variavel de ambiente ou tabela segura de integracoes.
Associar cada token a um admin_id/tenant especifico para impedir cross-tenant.
Aplicar rate limit por IP/token para evitar abuso.
Endpoints de API devem retornar JSON e nao depender de login de navegador.
Isentar CSRF apenas nos endpoints de API autenticados por token, mantendo CSRF nas telas comuns.
Registrar request_id, integration_name e event_id para auditoria.
Nunca salvar payload bruto completo com dados sensiveis sem mascara.

## 6.4 Payload principal: upsert de lead

| {   "external_id": "whatsapp_5512999999999",   "origem_integracao": "agente_veks_n8n",   "canal_origem": "WhatsApp",   "telefone": "5512999999999",   "whatsapp_jid": "5512999999999@s.whatsapp.net",   "message_id": "ABC123",   "nome": "Joao da Silva",   "email": "joao@email.com",   "tipo_atendimento": "orcamento",   "perfil_lead": "cliente_final",   "temperatura": "quente",   "tipo_projeto": "casa",   "cidade_obra": "Sao Jose dos Campos - SP",   "possui_terreno": "sim",   "possui_projeto": "sim",   "metragem_aproximada": "120 m2",   "prazo_desejado": "quer iniciar ainda este ano",   "padrao_acabamento": "medio",   "objetivo_construcao": "moradia propria",   "dor_principal": "previsibilidade e prazo",   "duvidas_tecnicas": ["durabilidade", "fixacao de moveis"],   "objeções": ["medo de infiltracao"],   "demanda": "Cliente deseja orcamento para casa em Light Steel Frame.",   "resumo_atendimento": "Cliente tem terreno e projeto, busca previsibilidade e quer avaliar orcamento.",   "ultima_mensagem_cliente": "Tenho a planta em PDF e queria um orcamento.",   "proxima_acao": "humano",   "necessita_humano": true,   "motivo_handoff": "Cliente possui projeto pronto e solicitou orcamento.",   "status_sugerido": "Em fila" } |
| --- |


## 6.5 Resposta esperada da API

| {   "success": true,   "action": "created",   "lead_id": 123,   "cliente_id": 45,   "status": "Em fila",   "necessita_humano": true,   "message": "Lead criado com sucesso." } |
| --- |


# 7. Mapeamento do JSON Veks para o CRM do SIGE

| Base Veks / n8n | Campo SIGE atual ou novo | Regra |
| --- | --- | --- |
| lead.nome | Lead.nome | Obrigatorio. Se ausente, criar nome temporario: Lead WhatsApp - telefone. |
| lead.telefone | Lead.contato / whatsapp_phone | Normalizar para busca e manter contato exibivel. |
| lead.origem | Lead.origem_id / canal_origem | Mapear origem WhatsApp nas listas mestre ou campo novo. |
| lead.status | Lead.status | Nao aceitar qualquer status da IA; converter para status valido do SIGE. |
| lead.tipo_atendimento | tipo_atendimento novo | Classificacao da intencao principal. |
| lead.perfil | perfil_lead novo | Persona/ICP identificada. |
| lead.temperatura | temperatura novo | quente, morno, frio, parceria ou fora de escopo. |
| projeto.tipo_projeto | Lead.tipo_obra_id ou campo texto | Mapear para tipo de obra quando houver correspondencia. |
| projeto.cidade_obra | Lead.localizacao | Cidade/bairro/local da obra. |
| projeto.possui_terreno | possui_terreno novo | Campo estruturado para follow-up e qualificacao. |
| projeto.possui_projeto | possui_projeto novo | Se sim e houver arquivo, acionar handoff. |
| projeto.metragem_aproximada | metragem_aproximada novo | Texto/numerico. Nao usar para prometer valor por m2. |
| diagnostico.dor_principal | dor_principal novo / Lead.observacao | Usado para abordagem comercial. |
| diagnostico.objeções | Lead.observacao ou tabela mensagem | Registrar de forma resumida. |
| proximo_passo.acao | proxima_acao novo | Define proximo movimento: humano, orcamento, reuniao, follow-up. |
| proximo_passo.necessita_humano | necessita_humano novo | Se true, gerar alerta interno. |
| proximo_passo.motivo_handoff | motivo_handoff novo | Explicacao para o vendedor. |


# 8. Esboco do workflow n8n V2

## 8.1 Workflow 1 - Entrada WhatsApp e atendimento IA

| [Webhook WhatsApp]   -> [Code: normalizar payload]   -> [IF: ignorar mensagens from_me / grupos / eventos invalidos]   -> [HTTP: baixar midia, se houver]   -> [Switch: texto / audio / imagem / documento]   -> [OpenAI/Whisper: transcrever audio]   -> [Vision/LLM: resumir imagem ou documento simples]   -> [HTTP SIGE: buscar/atualizar estado do lead]   -> [Vector Store/RAG: consultar base Veks]   -> [AI Agent Veks: responder e atualizar JSON]   -> [Structured Output Parser: separar resposta_cliente + dados_crm]   -> [Code: validar JSON e aplicar regras]   -> [HTTP SIGE: upsert lead]   -> [HTTP SIGE: registrar mensagem/historico]   -> [IF: necessita_humano?]        -> sim: [Notificar responsavel]        -> nao: continuar   -> [HTTP WhatsApp: enviar resposta]   -> [Log sucesso] |
| --- |


## 8.2 Workflow 2 - Handoff humano

| [Execute Workflow / Webhook interno]   -> [Receber lead_id + motivo_handoff + resumo]   -> [HTTP SIGE: marcar necessita_humano]   -> [Buscar responsavel no SIGE]   -> [Enviar alerta interno: WhatsApp, email ou Slack]   -> [Registrar historico: handoff solicitado]   -> [Opcional: pausar IA para aquele contato] |
| --- |


## 8.3 Workflow 3 - Agendamento tecnico

| [Agente identifica interesse em reuniao/visita]   -> [Coletar dados minimos]   -> [Google Calendar: consultar disponibilidade]   -> [IF: presencial ou online]        -> presencial: criar evento sem Meet + endereco/local        -> online: criar evento com Meet   -> [HTTP SIGE: registrar agendamento no lead]   -> [WhatsApp: confirmar ao cliente]   -> [Log e controle para nao duplicar] |
| --- |


## 8.4 Workflow 4 - Follow-up automatico

| [Schedule Trigger: 1x por dia ou conforme regra]   -> [HTTP SIGE: listar leads candidatos]   -> [Split in Batches]   -> [IF: possui handoff/humano ativo?]        -> sim: nao enviar automatico        -> nao: continuar   -> [AI: gerar mensagem curta com contexto]   -> [WhatsApp: enviar follow-up]   -> [HTTP SIGE: registrar follow-up enviado]   -> [Controle: limite de tentativas e janela de horario] |
| --- |


## 8.5 Workflow 5 - RAG/base de conhecimento Veks

| [Google Drive Trigger ou execucao manual]   -> [Baixar documentos aprovados]   -> [Extrair texto]   -> [Chunking]   -> [Embeddings]   -> [Vector Store]   -> [Log de documentos indexados]   -> [Revisao humana antes de respostas tecnicas sensiveis] |
| --- |


# 9. Configuracao node por node - MVP recomendado

| Ordem | Node n8n | Configuracao principal | Saida esperada |
| --- | --- | --- | --- |
| 1 | Webhook | POST; path exclusivo do provedor de WhatsApp; responder rapido com 200 quando possivel. | Payload bruto recebido. |
| 2 | Code - Normalizar WhatsApp | Criar objeto padrao: message_id, telefone, nome_contato, tipo, texto, media_url, timestamp, from_me, raw_minimo. | Mensagem normalizada. |
| 3 | IF - Ignorar evento | from_me=true, grupo, sem telefone, sem texto/midia, evento duplicado. | Somente mensagens validas seguem. |
| 4 | HTTP SIGE - Meta/Estado | Buscar dados do lead e listas mestre quando necessario. | Contexto do CRM. |
| 5 | Switch - Tipo mensagem | text, audio, image, document, unknown. | Rota correta de processamento. |
| 6 | OpenAI Audio / Vision | Transcrever ou resumir midia; se documento tecnico, marcar handoff. | Texto interpretavel pela IA. |
| 7 | Vector Store Retriever | Consultar base Veks: FAQ, objeções, regras, Light Steel Frame. | Trechos de contexto. |
| 8 | AI Agent Veks | Prompt mestre + estado JSON + regras de nao prometer preco/prazo/viabilidade. | Resposta ao cliente + JSON atualizado. |
| 9 | Structured Output Parser | Forcar saida com schema: resposta_cliente, dados_crm, handoff, confianca. | JSON confiavel. |
| 10 | Code - Validacao | Corrigir tipos, limitar status, exigir telefone, criar nome temporario se ausente. | Payload pronto para SIGE. |
| 11 | HTTP SIGE - Upsert Lead | POST /api/integracoes/crm/leads/upsert. | lead_id e action. |
| 12 | HTTP SIGE - Registrar Mensagem | Salvar mensagem entrada, resposta e resumo. | Historico persistido. |
| 13 | IF - Handoff | necessita_humano=true ou intencao=humano/projeto_pronto/duvida_critica. | Aciona responsavel. |
| 14 | HTTP WhatsApp - Enviar resposta | Enviar resposta final ao contato. | Cliente respondido. |
| 15 | Log | Salvar execucao, erros e tempo de resposta. | Monitoramento. |


# 10. Expressoes e pseudocodigo uteis no n8n

## 10.1 Payload interno padrao depois do normalizador

| {   "message_id": "{{ $json.body?.data?.key?.id // $json.body?.entry?.[0]?.changes?.[0]?.value?.messages?.[0]?.id }}",   "telefone": "{{ String($json.body?.data?.key?.remoteJid // $json.body?.from // '').replace(/\D/g, '') }}",   "nome_contato": "{{ $json.body?.data?.pushName // $json.body?.contacts?.[0]?.profile?.name // '' }}",   "tipo": "text",   "texto": "{{ $json.body?.data?.message?.conversation // $json.body?.text?.body // '' }}",   "media_url": null,   "timestamp": "{{ new Date().toISOString() }}",   "from_me": false,   "provedor": "whatsapp_adapter" } |
| --- |


## 10.2 Regra para nome temporario

| const telefone = item.telefone; if (!item.nome // item.nome.trim().length < 2) {   item.nome = `Lead WhatsApp - ${telefone}`; } return item; |
| --- |


## 10.3 Regra de handoff no Code node

| const d = item.dados_crm // {}; const motivos = []; if (d.possui_projeto === 'sim') motivos.push('Cliente possui projeto pronto'); if (d.intencao === 'humano') motivos.push('Cliente pediu atendimento humano'); if (d.tipo_atendimento === 'orcamento' && d.temperatura === 'quente') motivos.push('Lead quente solicitou orcamento'); if ((d.duvidas_tecnicas // []).length > 0 && d.confianca_tecnica === 'baixa') motivos.push('Duvida tecnica exige avaliacao');  item.necessita_humano = motivos.length > 0; item.motivo_handoff = motivos.join('; '); return item; |
| --- |


# 11. Prompt mestre revisado do agente Veks

| O prompt abaixo deve ser colocado no node de IA com as variaveis de contexto do lead, memoria da conversa e trechos RAG. Ele nao deve conter credenciais nem URLs internas sensiveis. |
| --- |


| Voce e a assistente comercial da Veks Engenharia, especializada em construcao em Light Steel Frame.  OBJETIVO: Atender clientes pelo WhatsApp de forma consultiva, clara e profissional, qualificar o projeto, responder duvidas com seguranca e conduzir para o proximo passo correto: orcamento, reuniao tecnica, envio de projeto, atendimento humano ou follow-up.  REGRAS CRITICAS: 1. Primeiro entenda o projeto e a dor do cliente. Nao comece empurrando a solucao. 2. Nao prometa preco por metro, prazo fechado, garantia, viabilidade tecnica ou resultado sem avaliacao da equipe. 3. Se o cliente pedir preco, explique que depende de projeto, metragem, padrao, localizacao e escopo. Colete dados. 4. Se o cliente enviar projeto, planta, documento, foto tecnica ou pedir confirmacao tecnica, marque handoff humano. 5. Faca uma pergunta por vez quando o cliente estiver confuso. 6. Nunca invente informacao tecnica. Se nao houver certeza, diga que a equipe tecnica avaliará. 7. Sempre atualize o JSON interno do lead. 8. Evite repetir pergunta ja respondida. 9. Use linguagem simples, humana, curta e adequada para WhatsApp.  DADOS MINIMOS PARA ORCAMENTO: - Nome - Cidade da obra - Tipo de projeto - Metragem aproximada - Se possui terreno - Se possui projeto - Prazo desejado - Objetivo da construcao  SAIDA OBRIGATORIA EM JSON: {   "resposta_cliente": "mensagem curta para enviar no WhatsApp",   "dados_crm": { ...campos atualizados... },   "necessita_humano": true/false,   "motivo_handoff": "texto ou null",   "confianca": "alta/media/baixa" } |
| --- |


# 12. Plano de implementacao por fases

| Fase | Entrega | Tarefas | Criterio de pronto |
| --- | --- | --- | --- |
| 0 - Preparacao | Definicao de provedor e campos | Escolher provedor WhatsApp; revisar listas mestre do CRM; definir responsaveis; revisar base tecnica Veks. | Checklist comercial e tecnico aprovado. |
| 1 - API SIGE MVP | Endpoints de integracao CRM | Criar blueprint, auth por token, upsert lead, registrar mensagens, meta/opcoes, logs. | n8n consegue criar/atualizar lead em ambiente teste. |
| 2 - Workflow n8n MVP | Atendimento texto + CRM | Webhook, normalizador, IA, parser, upsert SIGE, resposta WhatsApp, log. | Lead aparece no Kanban com historico e resposta enviada. |
| 3 - Handoff humano | Transferencia operacional | Campos necessita_humano/motivo; alerta interno; pausa da IA; historico no CRM. | Lead com projeto pronto aciona responsavel automaticamente. |
| 4 - Midias | Audio, imagens e documentos | Transcricao, resumo de imagem, documento tecnico gera handoff. | Audio vira texto e documento tecnico nao recebe resposta arriscada. |
| 5 - RAG | Base Veks versionada | Indexar FAQ, objeções, LSF, regras comerciais, apresentacao e materiais revisados. | Agente responde duvidas com base aprovada e sem inventar. |
| 6 - Agendamento | Reuniao/visita tecnica | Google Calendar, online/presencial separado, log no CRM, confirmacao. | Evento criado sem duplicidade e registrado no lead. |
| 7 - Follow-up | Retomada automatica controlada | Listar leads parados, limitar tentativas, enviar mensagens contextuais, registrar. | Follow-up envia apenas para leads elegiveis e nao insiste indevidamente. |
| 8 - Monitoramento | Producao robusta | Error Workflow, dashboards, alertas, metricas e revisao mensal dos leads. | Falhas sao rastreaveis e time sabe onde atuar. |


# 13. Checklist de credenciais e configuracoes

| Item | Onde configurar | Observacao de seguranca |
| --- | --- | --- |
| Token interno SIGE API | Credencial HTTP Header Auth no n8n + variavel de ambiente no SIGE | Nunca colar token em node, prompt ou JSON exportado. |
| URL base do SIGE | Variavel do workflow n8n | Separar homologacao e producao. |
| Provedor WhatsApp | Credencial propria do provedor no n8n | Confirmar formato atual do webhook antes de importar fluxo antigo. |
| OpenAI/modelo IA | Credencial nativa do n8n | Definir modelo, limite de tokens e custo maximo. |
| Vector Store | Supabase/Qdrant/Postgres conforme stack | Base RAG deve conter apenas material aprovado. |
| Google Calendar | Credencial OAuth no n8n | Separar calendario tecnico e regras de disponibilidade. |
| Canal de alerta interno | WhatsApp interno, email ou Slack | Nao expor dados sensiveis demais em alertas. |
| Logs | SIGE, Postgres ou n8n executions | Mascarar telefone quando exportar relatorios. |


# 14. Casos de teste obrigatorios

| Teste | Entrada simulada | Resultado esperado |
| --- | --- | --- |
| Lead novo sem nome | Cliente: "quanto custa uma casa em steel frame?" | Cria lead com nome temporario, status Em fila, pergunta cidade/tipo/terreno/projeto. |
| Lead novo com dados completos | Cliente informa nome, cidade, metragem, terreno e projeto. | Cria lead quente, necessita_humano=true, resumo no CRM. |
| Lead existente | Mesmo telefone volta dias depois. | Atualiza lead existente e nao duplica. |
| Projeto em PDF | Cliente envia planta/projeto. | Registra documento/mensagem, aciona handoff humano e evita analise tecnica automatica. |
| Pergunta preco por metro | "Qual valor por m2?" | Explica variacao sem prometer valor e coleta dados. |
| Pergunta tecnica sensivel | "Pode molhar? garante que nao infiltra?" | Resposta educativa com ressalva e possivel handoff. |
| Humano | "Quero falar com alguem" | Marca handoff e alerta responsavel. |
| Mensagem duplicada | Mesmo message_id recebido duas vezes. | Segunda execucao nao cria mensagem/lead duplicado. |
| Erro SIGE API | SIGE retorna 500. | Nao perde contexto; registra erro e notifica operador. |
| Erro WhatsApp send | Falha ao enviar resposta. | Registra falha e permite reprocessar. |
| Fora de escopo | Cliente pede servico que a Veks nao faz. | Responde com educacao, marca fora_escopo e encerra/nutre. |
| Parceria | Arquiteto quer parceria. | Classifica como parceria e aciona responsavel comercial. |


# 15. Principais riscos e correcoes

| Risco | Impacto | Correcao |
| --- | --- | --- |
| API WhatsApp mudou | Workflow antigo nao recebe campos esperados. | Criar normalizador/adaptador independente do provedor. |
| Lead duplicado | CRM poluido e atendimento confuso. | Idempotencia por telefone normalizado, e-mail, external_id e message_id. |
| IA promete preco/prazo | Risco comercial e juridico. | Prompt restritivo + validacao de resposta + handoff em temas sensiveis. |
| Handoff nao acontece | Lead quente fica preso na IA. | Regra estruturada no n8n + campo no CRM + alerta interno. |
| Workflow gigante | Manutencao dificil e falhas em cascata. | Separar em workflows menores. |
| Credenciais vazando em JSON | Risco de seguranca. | Usar credenciais nativas, remover pinData, revisar export antes de compartilhar. |
| RAG com conteudo nao revisado | Resposta tecnica errada. | Base aprovada por responsavel tecnico e versionamento. |
| Follow-up insistente | Experiencia ruim do cliente. | Limite de tentativas, janelas de horario e opt-out. |
| CSRF bloqueando API | n8n recebe erro 400. | Isentar somente rotas de API autenticadas por token. |
| Token unico para tudo | Dificuldade de auditoria e revogacao. | Token por tenant/integracao com nome, escopo e data de rotacao. |


# 16. Prompt para implementar no Replit/Codex

| Voce e especialista backend Flask + SQLAlchemy no projeto SIGE.  Objetivo: Implementar uma API interna segura para que o n8n crie, atualize e registre historico de leads no CRM nativo do SIGE, para o agente de atendimento da Veks Engenharia via WhatsApp.  Contexto: O CRM atual esta em crm_views.py e ja possui Lead, LeadHistorico, Cliente, listas mestre, Kanban, lista e mudanca de status. As rotas atuais sao de UI com login_required. Precisamos de endpoints JSON autenticados por token para automacoes n8n.  Criar arquivo: api_crm_integracoes.py  Blueprint: api_crm_integracoes_bp = Blueprint('api_crm_integracoes', __name__, url_prefix='/api/integracoes/crm')  Endpoints MVP: 1. GET /health 2. GET /meta/opcoes 3. POST /leads/upsert 4. POST /leads/<int:lead_id>/mensagens 5. POST /leads/<int:lead_id>/handoff  Regras obrigatorias: - Nao alterar comportamento das telas existentes do CRM. - Nao gravar direto no banco a partir do n8n sem passar pela API. - Usar Authorization Bearer por variavel de ambiente ou tabela segura de integracoes. - Resolver admin_id da integracao com seguranca. - Normalizar telefone removendo caracteres nao numericos. - Fazer upsert por external_id, whatsapp_phone/telefone, whatsapp_jid ou e-mail. - Se lead nao tiver nome, criar nome temporario: Lead WhatsApp - telefone. - Validar status contra status validos do CRM. - Atualizar apenas campos recebidos nao vazios, sem apagar dados bons ja existentes. - Registrar historico de criacao, atualizacao, mensagens e handoff. - Criar/vincular Cliente usando a logica existente quando possivel. - Retornar JSON padronizado com success, action, lead_id, cliente_id, status e message. - Incluir logs com request_id, integration_name e event_id/message_id. - Evitar armazenar payload bruto sensivel sem mascara. - Criar ou adaptar migracao para campos novos recomendados. - Adicionar registro do blueprint no app.py. - Documentar variaveis de ambiente necessarias. - Entregar exemplos de cURL e checklist de teste manual.  Nao fazer: - Nao expor token em codigo. - Nao criar proposta/obra automaticamente. - Nao remover regras de tenant/admin_id. - Nao quebrar crm_views.py. - Nao depender de sessao de navegador ou CSRF de tela para a API. |
| --- |


# 17. Criterios de aceite da entrega

| Modulo | Aceite minimo |
| --- | --- |
| SIGE API | Recebe payload n8n, autentica, cria/atualiza lead, registra historico e retorna JSON correto. |
| CRM | Lead aparece no Kanban/lista com dados principais, temperatura, proxima acao e handoff quando aplicavel. |
| n8n MVP | Recebe WhatsApp texto, conversa com IA, envia resposta e grava no SIGE. |
| Seguranca | Sem token exposto, sem pinData sensivel, API por Bearer, logs mascarados. |
| Handoff | Projeto pronto, humano solicitado e duvida sensivel geram alerta interno. |
| RAG | Agente usa base aprovada e nao inventa resposta tecnica. |
| Follow-up | Nao envia mensagem para lead com humano ativo e respeita limite de tentativas. |
| Monitoramento | Erros de API/WhatsApp/IA sao registrados e podem ser reprocessados. |


# 18. Recomendacao final

| Minha recomendacao e tratar essa implantacao como produto V2: primeiro colocar o CRM do SIGE para receber leads de forma robusta por API; depois conectar o n8n com WhatsApp e IA; por ultimo adicionar RAG, agenda, follow-up e metricas. Isso reduz risco, melhora manutencao e transforma o atendimento da Veks em uma entrada real do funil comercial do SIGE. |
| --- |


# 19. Checklist rapido para iniciar agora
Definir o provedor atual de WhatsApp e obter um exemplo real de webhook atualizado.
Validar no SIGE quais campos novos serao adicionados ao Lead e quais ficarao em tabela de mensagens/interacoes.
Implementar API interna do CRM em homologacao.
Criar workflow n8n MVP apenas com texto, IA, upsert lead e resposta WhatsApp.
Testar 12 cenarios obrigatorios com leads ficticios.
Revisar tecnicamente as respostas sobre Light Steel Frame com responsavel da Veks.
Ativar handoff humano antes de liberar para clientes reais.
Depois adicionar audio, documentos, RAG, agenda e follow-up.

# 20. Fontes internas consideradas
base_agente_n8n_veks.txt - base comercial, prompt, ICP, objeções, JSON incremental, arquitetura n8n e testes da Veks.
crm_views.py - rotas e regras atuais do CRM do SIGE, incluindo Kanban, lista, novo lead, edicao, status e vinculo com cliente.
manual/28_crm.md - descricao operacional do CRM de Leads do SIGE.
app.py - padrao de inicializacao, seguranca, CSRF, CORS e registro de blueprints do SIGE.
