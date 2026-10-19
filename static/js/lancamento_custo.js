document.addEventListener('DOMContentLoaded', function () {
    const custosPapel = window.CUSTOS_PAPEL || {};
    const custosOpPadrao = window.CUSTOS_OP_PADRAO || {};
    const camposCalculo = [
        'quantidade', 'milheiro', 'refugo_acerto_flexo', 'refugo_flexo',
        'refugo_acerto_sos', 'refugo_sos', 'refugo_pre_impresso',
        'valor_papel', 'cola', 'alca', 'mdo_alca', 'tinta'
    ];

    function parseNum(value) {
        const n = parseFloat(value);
        return Number.isFinite(n) ? n : 0;
    }

    function formatNum(value, decimals) {
        return value.toLocaleString('pt-BR', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    function getValue(name) {
        const field = document.querySelector('[name="' + name + '"]');
        return field ? field.value : '';
    }

    function setValue(name, value) {
        const field = document.querySelector('[name="' + name + '"]');
        if (field) {
            field.value = value;
        }
    }

    function isSacola() {
        const tipo = (getValue('tipo') || '').trim().toUpperCase();
        return tipo === 'SACOLA';
    }

    function isPapelBranco(papel) {
        const p = (papel || getValue('tipo_papel') || '').trim().toUpperCase();
        return p === 'BRANCO 110G' || p === 'BRANCO 110GRS' || p === 'BRANCO 90GRS' || p === 'BRANCO 80GRS';
    }

    function valorAlcaPadrao() {
        if (isPapelBranco()) {
            return custosOpPadrao.alca_branca || 0;
        }
        return custosOpPadrao.alca_natural || custosOpPadrao.alca || 0;
    }

    function aplicarRegraCartucho() {
        // Alça só entra em SACOLA; CARTUCHO e SEDA não usam
        if (isSacola()) {
            setValue('alca', valorAlcaPadrao());
            setValue('mdo_alca', custosOpPadrao.mdo_alca || 0);
        } else {
            setValue('alca', '0');
            setValue('mdo_alca', '0');
        }
    }

    function atualizarValorPapel() {
        const papel = getValue('tipo_papel');
        if (papel && custosPapel[papel] !== undefined) {
            setValue('valor_papel', custosPapel[papel]);
        }
    }

    function calcularCusto() {
        const quantidade = parseNum(getValue('quantidade'));
        const milheiro = parseNum(getValue('milheiro'));
        const refugoAcertoFlexo = parseNum(getValue('refugo_acerto_flexo'));
        const refugoFlexo = parseNum(getValue('refugo_flexo'));
        const refugoAcertoSos = parseNum(getValue('refugo_acerto_sos'));
        const refugoSos = parseNum(getValue('refugo_sos'));
        const refugoPreImpresso = parseNum(getValue('refugo_pre_impresso'));
        const valorPapel = parseNum(getValue('valor_papel'));
        const cola = parseNum(getValue('cola'));
        const alca = parseNum(getValue('alca'));
        const mdoAlca = parseNum(getValue('mdo_alca'));
        const tinta = parseNum(getValue('tinta'));

        const consumoUtil = (quantidade / 1000) * milheiro;
        const refugoTotal = refugoAcertoFlexo + refugoFlexo + refugoAcertoSos + refugoSos + refugoPreImpresso;
        const somaConsumo = consumoUtil + refugoTotal;

        const custoPapel = somaConsumo * valorPapel;
        const custoTinta = tinta * quantidade;
        const custoCola = cola * quantidade;
        const custoAlca = alca * quantidade;
        const custoMdoAlca = mdoAlca * quantidade;
        const custoPrevia = custoPapel + custoTinta + custoCola + custoAlca + custoMdoAlca;
        const milheiros = quantidade / 1000;
        const custoMilheiro = milheiros > 0 ? custoPrevia / milheiros : 0;

        document.getElementById('prev_consumo_util').textContent = formatNum(consumoUtil, 3);
        document.getElementById('prev_refugo_total').textContent = formatNum(refugoTotal, 3);
        document.getElementById('prev_soma_consumo').textContent = formatNum(somaConsumo, 3);
        document.getElementById('prev_custo_papel').textContent = formatNum(custoPapel, 2);
        document.getElementById('prev_custo_tinta').textContent = formatNum(custoTinta, 2);
        document.getElementById('prev_custo_cola').textContent = formatNum(custoCola, 2);
        document.getElementById('prev_custo_alca').textContent = formatNum(custoAlca, 2);
        document.getElementById('prev_custo_mdo_alca').textContent = formatNum(custoMdoAlca, 2);
        document.getElementById('prev_custo_previa').textContent = formatNum(custoPrevia, 2);
        document.getElementById('prev_custo_milheiro').textContent = formatNum(custoMilheiro, 2);
    }

    function preencherCamposComanda(data) {
        const campos = [
            'num_of', 'servico', 'quantidade', 'milheiro', 'refugo_acerto_flexo', 'refugo_flexo',
            'refugo_acerto_sos', 'refugo_sos', 'refugo_pre_impresso', 'tipo'
        ];

        campos.forEach(function (campo) {
            if (data[campo] !== undefined && data[campo] !== null) {
                setValue(campo, data[campo]);
            }
        });

        if (data.papel) {
            const selectPapel = document.getElementById('tipo_papel');
            const papel = data.papel;
            const optionExists = Array.from(selectPapel.options).some(function (opt) {
                return opt.value === papel;
            });
            if (!optionExists) {
                const opt = document.createElement('option');
                opt.value = papel;
                opt.textContent = papel;
                selectPapel.appendChild(opt);
            }
            selectPapel.value = papel;
            if (custosPapel[papel] !== undefined) {
                setValue('valor_papel', custosPapel[papel]);
            }
        }

        aplicarRegraCartucho();
        calcularCusto();
    }

    document.getElementById('num_of').addEventListener('blur', function () {
        const numOf = this.value.trim();
        if (!numOf) return;

        fetch(window.BUSCAR_OF_URL + '?num_of=' + encodeURIComponent(numOf))
            .then(function (response) {
                if (response.status === 404) return null;
                return response.json();
            })
            .then(function (data) {
                if (data && Object.keys(data).length > 0) {
                    preencherCamposComanda(data);
                }
            })
            .catch(function (error) {
                console.error('Erro ao buscar dados da OF:', error);
            });
    });

    document.getElementById('tipo').addEventListener('change', function () {
        aplicarRegraCartucho();
        calcularCusto();
    });

    document.getElementById('tipo_papel').addEventListener('change', function () {
        atualizarValorPapel();
        aplicarRegraCartucho();
        calcularCusto();
    });

    camposCalculo.forEach(function (campo) {
        const el = document.querySelector('[name="' + campo + '"]');
        if (el) {
            el.addEventListener('input', calcularCusto);
            el.addEventListener('change', calcularCusto);
        }
    });

    aplicarRegraCartucho();
    calcularCusto();

    // --- Lançamento de custo por pedido ---
    const numeroPedidoInput = document.getElementById('numero_pedido_busca');
    const btnBuscarPedido = document.getElementById('btn_buscar_pedido');
    const pedidosResultado = document.getElementById('pedidos_resultado');
    const pedidosTbody = document.getElementById('pedidos_tbody');
    const pedidosVazio = document.getElementById('pedidos_vazio');
    const pedidosMsg = document.getElementById('pedidos_msg');

    function mostrarMsgPedido(texto, tipo) {
        pedidosMsg.textContent = texto;
        pedidosMsg.className = 'pedidos-msg ' + (tipo || '');
        pedidosMsg.style.display = texto ? 'block' : 'none';
    }

    function renderizarPedidos(pedidos) {
        pedidosTbody.innerHTML = '';
        pedidosResultado.style.display = 'none';
        pedidosVazio.style.display = 'none';
        mostrarMsgPedido('', '');

        if (!pedidos || pedidos.length === 0) {
            pedidosVazio.style.display = 'block';
            return;
        }

        pedidos.forEach(function (item) {
            const tr = document.createElement('tr');
            tr.dataset.pedidoId = item.id;

            const custoAtual = item.custo !== null && item.custo !== undefined
                ? parseFloat(item.custo).toFixed(2)
                : '';

            tr.innerHTML =
                '<td>' + (item.fantasia || '') + '</td>' +
                '<td>' + (item.qtde_total != null ? item.qtde_total : '') + '</td>' +
                '<td>' + (item.medida || '') + '</td>' +
                '<td>' + (item.papel || '') + '</td>' +
                '<td>' + (item.grupo || '') + '</td>' +
                '<td><input type="number" step="0.01" class="custo-input" name="custo" value="' + custoAtual + '" placeholder="0,00"></td>' +
                '<td><button type="button" class="btn-lancar">Lançar</button></td>';

            const btnLancar = tr.querySelector('.btn-lancar');
            btnLancar.addEventListener('click', function () {
                lancarCustoPedido(tr, item.id);
            });

            pedidosTbody.appendChild(tr);
        });

        pedidosResultado.style.display = 'block';
    }

    function buscarPedidos() {
        const pedido = numeroPedidoInput.value.trim();
        if (!pedido) {
            mostrarMsgPedido('Informe o número do pedido.', 'erro');
            return;
        }

        btnBuscarPedido.disabled = true;
        mostrarMsgPedido('Buscando...', '');

        fetch(window.BUSCAR_PEDIDOS_URL + '?pedido=' + encodeURIComponent(pedido))
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok && result.data.erro) {
                    mostrarMsgPedido(result.data.erro, 'erro');
                    renderizarPedidos([]);
                    return;
                }
                renderizarPedidos(result.data);
            })
            .catch(function () {
                mostrarMsgPedido('Erro ao buscar pedidos.', 'erro');
            })
            .finally(function () {
                btnBuscarPedido.disabled = false;
            });
    }

    function lancarCustoPedido(tr, pedidoId) {
        const custoInput = tr.querySelector('.custo-input');
        const custo = custoInput.value.trim();
        const btn = tr.querySelector('.btn-lancar');

        if (!custo) {
            mostrarMsgPedido('Informe o valor do custo antes de lançar.', 'erro');
            custoInput.focus();
            return;
        }

        btn.disabled = true;
        mostrarMsgPedido('', '');

        var csrfMeta = document.querySelector('meta[name="csrf-token"]');
        fetch(window.LANCAR_CUSTO_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : ''
            },
            body: JSON.stringify({ pedido_id: pedidoId, custo: custo })
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (result.data.ok) {
                    mostrarMsgPedido(result.data.mensagem, 'sucesso');
                } else {
                    mostrarMsgPedido(result.data.mensagem || 'Erro ao lançar custo.', 'erro');
                }
            })
            .catch(function () {
                mostrarMsgPedido('Erro ao lançar custo.', 'erro');
            })
            .finally(function () {
                btn.disabled = false;
            });
    }

    btnBuscarPedido.addEventListener('click', buscarPedidos);
    numeroPedidoInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            buscarPedidos();
        }
    });
});
