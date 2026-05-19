/**
 * quick_create.js — Task #30
 * Utilitário de criação rápida de entidades via modal Bootstrap.
 *
 * Uso:
 *   quickCreate({
 *     title: 'Novo Insumo',
 *     endpoint: '/api/quick-create/insumo',
 *     fields: [
 *       { name: 'nome', label: 'Nome', type: 'text', required: true },
 *       { name: 'tipo', label: 'Tipo', type: 'select',
 *         options: [{value:'MATERIAL',label:'Material'}, ...] },
 *       { name: 'unidade', label: 'Unidade', type: 'text' },
 *     ],
 *     onSuccess: function(data) { ... }
 *   });
 */
(function () {
  'use strict';

  var MODAL_ID = 'quickCreateModal';

  function getOrCreateModal() {
    var existing = document.getElementById(MODAL_ID);
    if (existing) return existing;
    var div = document.createElement('div');
    div.className = 'modal fade';
    div.id = MODAL_ID;
    div.setAttribute('tabindex', '-1');
    div.setAttribute('aria-hidden', 'true');
    div.innerHTML =
      '<div class="modal-dialog modal-dialog-centered">' +
        '<div class="modal-content" id="quickCreateModalContent"></div>' +
      '</div>';
    document.body.appendChild(div);
    return div;
  }

  function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  function buildFieldHtml(field) {
    var id = 'qc_field_' + field.name;
    var required = field.required ? 'required' : '';
    var html = '<div class="mb-3">';
    html += '<label class="form-label fw-semibold" for="' + id + '">';
    html += escHtml(field.label);
    if (field.required) html += ' <span class="text-danger">*</span>';
    html += '</label>';

    if (field.type === 'select') {
      html += '<select class="form-select" id="' + id + '" name="' + field.name + '" ' + required + '>';
      if (!field.required) html += '<option value="">— Selecione —</option>';
      (field.options || []).forEach(function (opt) {
        var sel = field.default === opt.value ? ' selected' : '';
        html += '<option value="' + escHtml(opt.value) + '"' + sel + '>' + escHtml(opt.label) + '</option>';
      });
      html += '</select>';
    } else {
      var placeholder = field.placeholder ? ' placeholder="' + escHtml(field.placeholder) + '"' : '';
      var val = field.default ? ' value="' + escHtml(field.default) + '"' : '';
      html += '<input class="form-control" type="' + (field.type || 'text') + '" id="' + id + '"';
      html += ' name="' + field.name + '"' + required + placeholder + val + '>';
    }

    if (field.help) {
      html += '<div class="form-text">' + escHtml(field.help) + '</div>';
    }
    html += '</div>';
    return html;
  }

  window.quickCreate = function (config) {
    var modalEl = getOrCreateModal();
    var content = document.getElementById('quickCreateModalContent');

    var fieldsHtml = (config.fields || []).map(buildFieldHtml).join('');

    content.innerHTML =
      '<div class="modal-header">' +
        '<h5 class="modal-title"><i class="fas fa-plus-circle me-2 text-success"></i>' + escHtml(config.title || 'Criar') + '</h5>' +
        '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>' +
      '</div>' +
      '<div class="modal-body">' +
        '<div id="qcErrorAlert" class="alert alert-danger d-none py-2"></div>' +
        '<form id="qcForm" novalidate>' +
          fieldsHtml +
        '</form>' +
      '</div>' +
      '<div class="modal-footer">' +
        '<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>' +
        '<button type="button" class="btn btn-success" id="qcSaveBtn">' +
          '<i class="fas fa-save me-1"></i>Salvar' +
        '</button>' +
      '</div>';

    var bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();

    var saveBtn = document.getElementById('qcSaveBtn');
    var errorAlert = document.getElementById('qcErrorAlert');
    var form = document.getElementById('qcForm');

    saveBtn.addEventListener('click', function () {
      errorAlert.classList.add('d-none');
      errorAlert.textContent = '';

      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }

      var payload = {};
      (config.fields || []).forEach(function (field) {
        var el = form.querySelector('[name="' + field.name + '"]');
        if (el) payload[field.name] = el.value;
      });

      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Salvando…';

      fetch(config.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then(function (resp) {
          return resp.json().then(function (data) {
            return { ok: resp.ok, data: data };
          });
        })
        .then(function (result) {
          saveBtn.disabled = false;
          saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>Salvar';

          if (!result.ok || result.data.erro) {
            errorAlert.textContent = result.data.erro || 'Erro ao salvar.';
            errorAlert.classList.remove('d-none');
            return;
          }

          bsModal.hide();
          if (typeof config.onSuccess === 'function') {
            config.onSuccess(result.data);
          }
        })
        .catch(function (err) {
          saveBtn.disabled = false;
          saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>Salvar';
          errorAlert.textContent = 'Erro de conexão: ' + err.message;
          errorAlert.classList.remove('d-none');
        });
    });
  };

  /**
   * Injeta uma nova opção em um <select> nativo e a seleciona.
   */
  window.qcInjectOption = function (selectEl, id, label) {
    if (!selectEl) return;
    var opt = document.createElement('option');
    opt.value = id;
    opt.textContent = label;
    opt.selected = true;
    selectEl.appendChild(opt);
    selectEl.value = id;
    selectEl.dispatchEvent(new Event('change', { bubbles: true }));
  };

  /**
   * Injeta uma nova opção em uma instância TomSelect e a seleciona.
   */
  window.qcInjectTomSelect = function (tsInstance, id, label, extraData) {
    if (!tsInstance) return;
    var item = Object.assign({ id: String(id), nome: label }, extraData || {});
    item[tsInstance.settings.valueField || 'id'] = String(id);
    item[tsInstance.settings.labelField || 'nome'] = label;
    tsInstance.addOption(item);
    tsInstance.setValue(String(id));
  };
})();
