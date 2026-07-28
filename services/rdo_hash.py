#!/usr/bin/env python3
"""Hash canônico do RDO — SIGE Fase 5.

Serve à parte "integridade" da assinatura: um SHA-256 sobre uma
representação DETERMINÍSTICA do conteúdo declarado do RDO. Se alguém
mexer no documento depois de assinado — inclusive por UPDATE direto no
banco, driblando a guarda `before_flush` — a verificação acusa.

O que ENTRA no payload: os campos que a pessoa declarou (clima, comentário,
subatividades e percentuais, equipe e horas, equipamentos, ocorrências,
apontamentos de cronograma) mais a IDENTIDADE das fotos.

O que NÃO entra, e por quê:

  * **Os bytes das fotos.** A Task 15 do plano migra `rdo_foto` de três
    cópias base64 no banco para arquivo em disco. Se o hash cobrisse
    bytes, toda assinatura anterior viraria "adulterada" por uma mudança
    que não tocou em nada que a pessoa declarou. Entram
    `(id, nome_original, descricao)` — identidade e legenda.
  * **`updated_at`, `created_at`, `status`, `estado`.** São metadados do
    sistema; o estado muda por transição legítima depois da assinatura
    (assinado → aprovado) e não pode invalidar nada.
  * **Campos derivados** (`quantidade_acumulada`, `percentual_realizado`
    consolidado). São recalculados pelo `recomputar_cadeia`
    (services/cronograma_apontamento_service.py) quando um RDO
    ANTERIOR é corrigido — não é adulteração deste documento.

Formato: JSON com `sort_keys=True`, `ensure_ascii=False`,
`separators=(',', ':')`, UTF-8. Números normalizados com
`round(float(x), 4)` para que 8.0 e 8 gerem o mesmo hash. Coleções
ordenadas por chave TOTAL — a linha inteira, nunca um prefixo dela e
nunca a ordem de inserção (ver `_ordem_total`).
"""
from __future__ import annotations

import hashlib
import json
import logging

logger = logging.getLogger('rdo.hash')

VERSAO_PAYLOAD = 1  # muda se o conjunto de campos mudar; vai dentro do hash


def _num(valor):
    """Normaliza número para o payload. None continua None."""
    if valor is None:
        return None
    try:
        return round(float(valor), 4)
    except (TypeError, ValueError):
        return None


def _txt(valor):
    """Normaliza texto: None e '' são a mesma coisa (None)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _ordem_total(linhas):
    """Ordena as linhas de uma coleção por uma chave TOTAL — a linha inteira.

    Chave parcial não serve aqui. `sorted` é estável: duas linhas que
    empatam na chave mantêm a ordem de ENTRADA, e a entrada vem de um
    SELECT sem ORDER BY — ordem que o Postgres não garante. O payload
    deixava de ser canônico exatamente quando havia repetição.

    Exemplo do que quebrava: dois equipamentos "Betoneira, qtd 1" (4h e
    6h) empatam na chave `(nome, quantidade)` que este módulo usava. O
    mesmo conteúdo gerava dois hashes conforme a ordem devolvida pelo
    banco — e a verificação acusaria adulteração num RDO intacto.

    Comparação por texto porque a linha mistura None, número e string, e
    `None < str` levanta em Python 3. Não precisa ser uma ordem
    *semântica*: precisa ser sempre a MESMA.

    `VERSAO_PAYLOAD` NÃO muda com esta correção, de propósito. Onde não
    havia empate a chave parcial já determinava a ordem sozinha, então os
    bytes continuam idênticos e as assinaturas já gravadas seguem
    verificando. Só mudam os payloads que eram ambíguos — e o hash deles
    nunca foi confiável.
    """
    return sorted(linhas,
                  key=lambda linha: ['' if x is None else str(x)
                                     for x in linha])


def payload_canonico(rdo) -> dict:
    """Representação determinística do conteúdo declarado do RDO."""
    from models import (RDOApontamentoCronograma, RDOEquipamento, RDOFoto,
                        RDOMaoObra, RDOOcorrencia, RDOServicoSubatividade)

    cabecalho = {
        'versao': VERSAO_PAYLOAD,
        'rdo_id': rdo.id,
        'numero_rdo': _txt(rdo.numero_rdo),
        'obra_id': rdo.obra_id,
        'data_relatorio': (rdo.data_relatorio.isoformat()
                           if rdo.data_relatorio else None),
        'local': _txt(rdo.local),
        'clima_geral': _txt(rdo.clima_geral),
        'temperatura_media': _txt(rdo.temperatura_media),
        'umidade_relativa': _num(rdo.umidade_relativa),
        'vento_velocidade': _txt(rdo.vento_velocidade),
        'precipitacao': _txt(rdo.precipitacao),
        'condicoes_trabalho': _txt(rdo.condicoes_trabalho),
        'observacoes_climaticas': _txt(rdo.observacoes_climaticas),
        'comentario_geral': _txt(rdo.comentario_geral),
        'criado_por_id': rdo.criado_por_id,
    }

    subs = _ordem_total(
        [_txt(s.nome_subatividade), s.servico_id,
         _num(s.percentual_conclusao), _num(s.quantidade_produzida),
         _txt(s.observacoes_tecnicas)]
        for s in RDOServicoSubatividade.query.filter_by(rdo_id=rdo.id).all())

    mao_obra = _ordem_total(
        [m.funcionario_id, _txt(m.funcao_exercida),
         _num(m.horas_trabalhadas), m.subatividade_id,
         m.tarefa_cronograma_id]
        for m in RDOMaoObra.query.filter_by(rdo_id=rdo.id).all())

    equipamentos = _ordem_total(
        [_txt(e.nome_equipamento), _num(e.quantidade), _num(e.horas_uso),
         _txt(e.estado_conservacao)]
        for e in RDOEquipamento.query.filter_by(rdo_id=rdo.id).all())

    ocorrencias = _ordem_total(
        [_txt(o.tipo_ocorrencia), _txt(o.severidade),
         _txt(o.descricao_ocorrencia), _txt(o.acoes_corretivas)]
        for o in RDOOcorrencia.query.filter_by(rdo_id=rdo.id).all())

    # Só o que a pessoa DIGITOU no dia. `quantidade_acumulada` e
    # `percentual_realizado` são derivados e podem ser recalculados pelo
    # recomputo em cadeia de um RDO anterior.
    apontamentos = _ordem_total(
        [a.tarefa_cronograma_id, _txt(getattr(a, 'tipo_apontamento', None)),
         _num(a.quantidade_executada_dia),
         _num(getattr(a, 'percentual_acumulado', None))]
        for a in RDOApontamentoCronograma.query.filter_by(rdo_id=rdo.id).all())

    fotos = _ordem_total(
        [f.id, _txt(f.nome_original) or _txt(f.nome_arquivo),
         _txt(f.descricao) or _txt(f.legenda)]
        for f in RDOFoto.query.filter_by(rdo_id=rdo.id).all())

    return {
        **cabecalho,
        'subatividades': subs,
        'mao_obra': mao_obra,
        'equipamentos': equipamentos,
        'ocorrencias': ocorrencias,
        'apontamentos': apontamentos,
        'fotos': fotos,
    }


def serializar(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), default=str)


def calcular_hash(rdo) -> str:
    """SHA-256 hexdigest (64 chars) do payload canônico do RDO."""
    texto = serializar(payload_canonico(rdo))
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def verificar_integridade(assinatura) -> bool:
    """True se o RDO continua batendo com o hash gravado na assinatura.

    Falha FECHADA: qualquer erro devolve False e loga. Uma verificação
    que não conseguiu rodar não é uma verificação bem-sucedida.
    """
    try:
        if assinatura is None or assinatura.rdo is None:
            return False
        if (assinatura.algoritmo or 'sha256') != 'sha256':
            logger.warning('[rdo-hash] algoritmo desconhecido %r na '
                           'assinatura %s', assinatura.algoritmo,
                           assinatura.id)
            return False
        return calcular_hash(assinatura.rdo) == assinatura.hash_conteudo
    except Exception:
        logger.exception('[rdo-hash] falha ao verificar assinatura %s',
                         getattr(assinatura, 'id', None))
        return False
