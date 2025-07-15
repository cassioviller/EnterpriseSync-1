// JavaScript corrigido para RDO - SIGE v6.3
// Correção de bugs críticos identificados

// ===== INICIALIZAÇÃO PRINCIPAL =====
$(document).ready(function() {
    console.log("Inicializando RDO v6.3...");
    
    // Aguardar carregamento completo
    setTimeout(function() {
        inicializarDropdownObraCorrigido();
        inicializarEventosFormulario();
        
        console.log("RDO v6.3 inicializado com sucesso!");
    }, 500);
});

// ===== DROPDOWN DE OBRAS =====
function inicializarDropdownObraCorrigido() {
    const obraSelect = $("#obra_select");
    console.log("Inicializando dropdown de obras...");
    
    // Carregar todas as obras
    $.get("/api/obras/todas")
        .done(function(obras) {
            console.log("Obras carregadas:", obras.length);
            
            // Limpar e popular
            obraSelect.empty().append('<option value="">Selecione a obra...</option>');
            
            obras.forEach(function(obra) {
                const opcao = new Option(
                    `${obra.nome} (${obra.codigo})`, 
                    obra.id
                );
                obraSelect.append(opcao);
            });
            
            // Inicializar Select2
            if (obras.length > 0) {
                obraSelect.select2({
                    placeholder: "Selecione a obra...",
                    allowClear: true,
                    width: '100%'
                });
            }
        })
        .fail(function(xhr, status, error) {
            console.error("Erro ao carregar obras:", error);
            obraSelect.empty().append('<option value="">Erro ao carregar obras</option>');
        });
}

// ===== FUNCIONÁRIOS =====
function adicionarFuncionario() {
    const container = document.getElementById("container_funcionarios");
    const template = document.getElementById("template_funcionario");
    
    if (!template) {
        console.error("Template de funcionário não encontrado!");
        return;
    }
    
    const novoItem = template.cloneNode(true);
    novoItem.style.display = "block";
    novoItem.id = `funcionario_${Date.now()}`;
    
    container.appendChild(novoItem);
    
    // Inicializar Select2 no novo funcionário
    inicializarFuncionarioSelect(novoItem);
    
    console.log("Funcionário adicionado ao RDO");
}

function inicializarFuncionarioSelect(container) {
    const select = $(container).find(".funcionario-select");
    
    // Carregar funcionários
    $.get("/api/funcionarios/todos")
        .done(function(funcionarios) {
            console.log("Funcionários carregados:", funcionarios.length);
            
            // Popular select
            select.empty().append('<option value="">Selecione o funcionário...</option>');
            
            funcionarios.forEach(function(func) {
                select.append(new Option(
                    `${func.nome} (${func.codigo})`, 
                    func.id
                ));
            });
            
            // Inicializar Select2
            select.select2({
                placeholder: "Digite para buscar funcionário...",
                allowClear: true,
                width: '100%'
            });
            
            // Evento de seleção
            select.on("select2:select", function(e) {
                const funcionarioId = e.params.data.id;
                carregarDadosPonto(container, funcionarioId);
            });
        })
        .fail(function() {
            select.empty().append('<option value="">Erro ao carregar funcionários</option>');
        });
}

function carregarDadosPonto(container, funcionarioId) {
    const dataRDO = $("#data_relatorio").val();
    
    if (!funcionarioId || !dataRDO) {
        habilitarPreenchimentoManual(container);
        return;
    }
    
    // Buscar dados do ponto
    const url = `/api/ponto/funcionario/${funcionarioId}/data/${dataRDO}`;
    
    $.get(url)
        .done(function(data) {
            if (data.success && data.registro_ponto) {
                preencherDadosPonto(container, data.registro_ponto);
                mostrarMensagem(container, "Dados do ponto carregados automaticamente", "success");
            } else {
                habilitarPreenchimentoManual(container);
                mostrarMensagem(container, "Ponto não encontrado - preencha manualmente", "warning");
            }
        })
        .fail(function() {
            habilitarPreenchimentoManual(container);
            mostrarMensagem(container, "Erro ao buscar ponto - preencha manualmente", "warning");
        });
}

function preencherDadosPonto(container, registro) {
    const campos = {
        ".hora-entrada": registro.hora_entrada || "",
        ".hora-saida": registro.hora_saida || "",
        ".total-horas": registro.horas_trabalhadas || "0.0"
    };
    
    // Preencher campos
    Object.keys(campos).forEach(selector => {
        const campo = container.querySelector(selector);
        if (campo) {
            campo.value = campos[selector];
            campo.readOnly = true;
        }
    });
    
    // Marcar como presente
    const checkbox = container.querySelector('input[type="checkbox"]');
    if (checkbox) checkbox.checked = true;
}

function habilitarPreenchimentoManual(container) {
    const campos = [".hora-entrada", ".hora-saida", ".total-horas"];
    
    campos.forEach(selector => {
        const campo = container.querySelector(selector);
        if (campo) {
            campo.value = "";
            campo.readOnly = false;
        }
    });
    
    const checkbox = container.querySelector('input[type="checkbox"]');
    if (checkbox) checkbox.checked = false;
}

function mostrarMensagem(container, mensagem, tipo) {
    // Remover mensagem anterior
    const mensagemAnterior = container.querySelector(".mensagem-status");
    if (mensagemAnterior) {
        mensagemAnterior.remove();
    }
    
    // Criar nova mensagem
    const div = document.createElement("div");
    div.className = `alert alert-${tipo} alert-sm mt-2 mensagem-status`;
    div.innerHTML = `<small>${mensagem}</small>`;
    
    const cardBody = container.querySelector(".card-body");
    if (cardBody) {
        cardBody.appendChild(div);
        
        // Remover após 5 segundos
        setTimeout(() => {
            if (div.parentNode) {
                div.remove();
            }
        }, 5000);
    }
}

function removerFuncionario(button) {
    const funcionarioItem = button.closest('.funcionario-item');
    if (funcionarioItem) {
        funcionarioItem.remove();
        console.log("Funcionário removido do RDO");
    }
}

// ===== EVENTOS DO FORMULÁRIO =====
function inicializarEventosFormulario() {
    // Validação de data
    $("#data_relatorio").on("change", function() {
        const data = $(this).val();
        if (data) {
            const dataObj = new Date(data);
            const hoje = new Date();
            
            if (dataObj > hoje) {
                alert("A data do relatório não pode ser futura!");
                $(this).val("");
            }
        }
    });
    
    // Calcular horas automaticamente
    $(document).on("change", ".hora-entrada, .hora-saida", function() {
        const container = $(this).closest(".funcionario-item");
        calcularHorasAutomaticamente(container[0]);
    });
}

function calcularHorasAutomaticamente(container) {
    const horaEntrada = container.querySelector(".hora-entrada").value;
    const horaSaida = container.querySelector(".hora-saida").value;
    const totalHoras = container.querySelector(".total-horas");
    
    if (horaEntrada && horaSaida && totalHoras && !totalHoras.readOnly) {
        try {
            const entrada = new Date(`2000-01-01T${horaEntrada}:00`);
            const saida = new Date(`2000-01-01T${horaSaida}:00`);
            
            if (saida > entrada) {
                const diffMs = saida - entrada;
                const diffHours = diffMs / (1000 * 60 * 60);
                
                // Considerar intervalo de almoço (1 hora)
                const horasLiquidas = Math.max(0, diffHours - 1);
                
                totalHoras.value = horasLiquidas.toFixed(1);
            }
        } catch (e) {
            console.error("Erro ao calcular horas:", e);
        }
    }
}

// ===== ENVIO DO FORMULÁRIO =====
function salvarRDO() {
    const formData = new FormData(document.getElementById("form_rdo"));
    
    $.ajax({
        url: "/api/rdo/salvar",
        method: "POST",
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            if (response.success) {
                alert("RDO salvo como rascunho!");
                window.location.href = "/rdo";
            } else {
                alert("Erro ao salvar: " + response.message);
            }
        },
        error: function() {
            alert("Erro de conexão ao salvar RDO");
        }
    });
}

function finalizarRDO() {
    if (!validarFormulario()) {
        return;
    }
    
    const formData = new FormData(document.getElementById("form_rdo"));
    formData.append("finalizar", "true");
    
    $.ajax({
        url: "/api/rdo/finalizar",
        method: "POST",
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            if (response.success) {
                alert("RDO finalizado com sucesso!");
                window.location.href = "/rdo";
            } else {
                alert("Erro ao finalizar: " + response.message);
            }
        },
        error: function() {
            alert("Erro de conexão ao finalizar RDO");
        }
    });
}

function validarFormulario() {
    const dataRelatorio = $("#data_relatorio").val();
    const obraId = $("#obra_select").val();
    
    if (!dataRelatorio) {
        alert("Por favor, selecione a data do relatório!");
        return false;
    }
    
    if (!obraId) {
        alert("Por favor, selecione a obra!");
        return false;
    }
    
    // Verificar se há pelo menos um funcionário
    const funcionarios = document.querySelectorAll(".funcionario-item[style*='block']");
    if (funcionarios.length === 0) {
        alert("Adicione pelo menos um funcionário ao RDO!");
        return false;
    }
    
    // Verificar se os funcionários têm dados válidos
    let funcionariosValidos = 0;
    funcionarios.forEach(func => {
        const select = func.querySelector(".funcionario-select");
        if (select && select.value) {
            funcionariosValidos++;
        }
    });
    
    if (funcionariosValidos === 0) {
        alert("Selecione pelo menos um funcionário válido!");
        return false;
    }
    
    return true;
}

// ===== UTILITÁRIOS =====
function limparFormulario() {
    if (confirm("Tem certeza que deseja limpar todos os dados?")) {
        document.getElementById("form_rdo").reset();
        document.getElementById("container_funcionarios").innerHTML = "";
        $("#obra_select").val("").trigger("change");
        console.log("Formulário limpo");
    }
}

// Log para debug
console.log("JavaScript RDO v6.3 carregado com correções críticas");