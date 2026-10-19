document.addEventListener('DOMContentLoaded', () => {

    // Preferência: valores injetados pelo servidor (cadastro no banco). Fallback vazio.
    const weightTolerances = window.WEIGHT_TOLERANCES || {};
    const IDEAL_SPEED_RATES = window.IDEAL_SPEED_RATES || {};
    const IDEAL_SETUP_TIMES_MIN={1:15.0,2:22.5,3:32.5};
    const IDEAL_SCRAP_RATES_SOS_PCT={'BRANCO 110G':8.0,'BRANCO 90GRS':6.0,'BRANCO 80GRS':6.0,'BAG 100GRS':6.0,'BAG 80GRS':6.0,'BAG 70GRS':8.0,'COLLEY 100G':8.0,'ECO 70GRS':10.0,'MONOL 70GRS':10.0,'MONOL 70GR':10.0,'MG 25GRS':10.0,'RU 32GRS':10.0,'KRAFT 35GRS':10.0};
    
    function getSeconds(t){if(!t)return 0;const[h,m]=t.split(':').map(Number);return(h*3600)+(m*60);}
    function getProdSeconds(inicio,fim){if(!inicio||!fim)return 0;let d=getSeconds(fim)-getSeconds(inicio);return d<0?d+86400:d;}
    const SOS_EXTRA_DAYS={
        2:{checkbox:'add_second_day',fields:'second_day_fields',inicio:'inicio_prod_2',fim:'fim_prod_2'},
        3:{checkbox:'add_third_day',fields:'third_day_fields',inicio:'inicio_prod_3',fim:'fim_prod_3'},
        4:{checkbox:'add_fourth_day',fields:'fourth_day_fields',inicio:'inicio_prod_4',fim:'fim_prod_4'}
    };
    const IMPRESSORA_EXTRA_DAYS={
        2:{checkbox:'add_impressora_second_day',fields:'impressora_second_day_fields',inicio:'inicio_prod_impressora_2',fim:'fim_prod_impressora_2'},
        3:{checkbox:'add_impressora_third_day',fields:'impressora_third_day_fields',inicio:'inicio_prod_impressora_3',fim:'fim_prod_impressora_3'},
        4:{checkbox:'add_impressora_fourth_day',fields:'impressora_fourth_day_fields',inicio:'inicio_prod_impressora_4',fim:'fim_prod_impressora_4'}
    };
    function getExtraDayProdSeconds(extraDaysConfig,dayNum){
        const d=extraDaysConfig[dayNum];
        if(!document.getElementById(d.checkbox).checked)return 0;
        return getProdSeconds(document.querySelector(`[name=${d.inicio}]`).value,document.querySelector(`[name=${d.fim}]`).value);
    }
    function setupExtraDayToggle(checkboxId,fieldsId){
        document.getElementById(checkboxId).addEventListener('change',function(){
            document.getElementById(fieldsId).style.display=this.checked?'grid':'none';
            calcPreview();
        });
    }
    function setupExtraDayToggles(extraDaysConfig){
        [2,3,4].forEach(dayNum=>setupExtraDayToggle(extraDaysConfig[dayNum].checkbox,extraDaysConfig[dayNum].fields));
    }
    function showExtraDaysIfFilled(extraDaysConfig){
        [2,3,4].forEach(dayNum=>{
            const d=extraDaysConfig[dayNum];
            if(document.querySelector(`[name=${d.inicio}]`).value){
                document.getElementById(d.checkbox).checked=true;
                document.getElementById(d.fields).style.display='grid';
            }
        });
    }

    function validateMilheiro() {
        const milheiroInput = document.querySelector('[name=milheiro]');
        const milheiroValue = parseFloat(milheiroInput.value);
        if (!milheiroValue) return;

        const formato = document.querySelector('[name=formato]').value;
        const papel = document.querySelector('[name=papel]').value;

        const tolerance = weightTolerances[papel] ? weightTolerances[papel][formato] : null;

        if (tolerance) {
            // Substituído alert() por um console.warn() para evitar pop-ups no navegador
            if (milheiroValue < tolerance.min) {
                alert(`Peso digitado abaixo do minimo Aceitável: ${tolerance.min.toFixed(2)} Kg`);
                milheiroInput.style.borderColor = 'red';
            } else if (milheiroValue > tolerance.max) {
                alert(`Peso digitado acima do Máximo Aceitavel: ${tolerance.max.toFixed(2)} Kg`);
                milheiroInput.style.borderColor = 'red';
            } else {
                milheiroInput.style.borderColor = '#ccc';
            }
        } else {
            milheiroInput.style.borderColor = '#ccc';
        }
    }
    
    window.calcPreview = function() {
        const m=parseFloat(document.querySelector('[name=milheiro]').value)||0,
              rf=parseFloat(document.querySelector('[name=refugo_flexo]').value)||0,
              rpi=parseFloat(document.querySelector('[name=refugo_pre_impresso]').value)||0,
              rs=parseFloat(document.querySelector('[name=refugo_sos]').value)||0,
              raf=parseFloat(document.querySelector('[name=refugo_acerto_flexo]').value)||0,
              ras=parseFloat(document.querySelector('[name=refugo_acerto_sos]').value)||0,
              r=rf+rpi+rs+raf+ras, // Calcula refugo total como soma dos 5 campos
              q=parseInt(document.querySelector('[name=quantidade]').value)||0,
              qflexo=parseInt(document.querySelector('[name=quantidade_impressora]').value)||0,
              maquina=document.querySelector('[name=sos]').value, // Usa SOS ao invés de maquina
              formato=document.querySelector('[name=formato]').value,
              papel=document.querySelector('[name=papel]').value,
              qtd_cliches=parseInt(document.querySelector('[name=qtd_cliches]').value)||0;
        
        // Calcula tempo de produção SOS (dias 1 a 4)
        const actual_prod_time_s=getProdSeconds(document.querySelector('[name=inicio_prod]').value,document.querySelector('[name=fim_prod]').value)
            +getExtraDayProdSeconds(SOS_EXTRA_DAYS,2)+getExtraDayProdSeconds(SOS_EXTRA_DAYS,3)+getExtraDayProdSeconds(SOS_EXTRA_DAYS,4);
        
        // Calcula tempo de acerto SOS
        let actual_setup_time_s=0;const ia=document.querySelector('[name=inicio_acerto]').value,fa=document.querySelector('[name=fim_acerto]').value;if(ia&&fa){let d=getSeconds(fa)-getSeconds(ia);actual_setup_time_s=d<0?d+86400:d;}
        
        // Calcula tempo de produção Impressora (dias 1 a 4)
        const actual_prod_time_impressora=getProdSeconds(document.querySelector('[name=inicio_prod_impressora]').value,document.querySelector('[name=fim_prod_impressora]').value)
            +getExtraDayProdSeconds(IMPRESSORA_EXTRA_DAYS,2)+getExtraDayProdSeconds(IMPRESSORA_EXTRA_DAYS,3)+getExtraDayProdSeconds(IMPRESSORA_EXTRA_DAYS,4);
        
        // Calcula tempo de acerto Impressora
        let actual_setup_time_impressora=0;
        const ia_imp=document.querySelector('[name=inicio_acerto_impressora]').value;
        const fa_imp=document.querySelector('[name=fim_acerto_impressora]').value;
        if(ia_imp&&fa_imp){let d=getSeconds(fa_imp)-getSeconds(ia_imp);actual_setup_time_impressora=d<0?d+86400:d;}
        
        // Calcula refugos separados
        const rsos = rpi + rs + ras; // Refugo SOS (soma dos 3 tipos referentes a SOS)
        const rflexo = rf + raf; // Refugo Flexo (soma dos 2 tipos referentes a Flexo)
        
        // Calcula perdas, velocidade, peso e refugo
        const perdas_un=m>0?((rsos+rflexo)*1000)/m:0;
        const actual_speed_un_min=actual_prod_time_s>0?(q/(actual_prod_time_s/60)):0;
        const actual_speed_un_min_flexo=actual_prod_time_impressora>0?(qflexo/(actual_prod_time_impressora/60)):0;
        const kg_pu=m>0?m/1000:0;
        const peso_boas_sos=(q*kg_pu);
        const peso_boas_flexo=(qflexo*kg_pu);
        
        // Calcula porcentagem de refugo SOS
        const actual_scrap_pct_sos=(peso_boas_sos+rsos)>0?(rsos/(peso_boas_sos+rsos))*100:0;
        
        // Calcula porcentagem de refugo Impressora
        const actual_scrap_pct_flexo=(peso_boas_flexo+rflexo)>0?(rflexo/(peso_boas_flexo+rflexo))*100:0;
        
        // Para o gauge de refugo, usa o refugo SOS (que é o principal)
        const actual_scrap_pct=actual_scrap_pct_sos;
        
        let ideal_speed_un_h = 0;
        if (maquina === 'APLA-2R') {
            ideal_speed_un_h = 3000.0;
        } else if (maquina === 'IMPRESSORA') {
            ideal_speed_un_h = 8000.0;
        } else {
            ideal_speed_un_h = IDEAL_SPEED_RATES[formato] || 0;
        }
        const ideal_speed_un_min = ideal_speed_un_h / 60;

        const speed_performance=ideal_speed_un_min>0?(actual_speed_un_min/ideal_speed_un_min):0;
        const ideal_setup_time_s=(IDEAL_SETUP_TIMES_MIN[qtd_cliches]||0)*60;const setup_performance=actual_setup_time_s>0?(ideal_setup_time_s/actual_setup_time_s):1;
        let ideal_scrap_pct=1.0;if(maquina.startsWith('SOS')){ideal_scrap_pct=IDEAL_SCRAP_RATES_SOS_PCT[papel]||100.0;}
        const actual_yield=100.0-actual_scrap_pct_sos;const ideal_yield=100.0-ideal_scrap_pct;const scrap_performance=ideal_yield>0?(actual_yield/ideal_yield):0;
        const total_efficiency = (speed_performance * setup_performance * scrap_performance) * 100;
        
        // Atualiza os campos hidden com os valores calculados
        const refugoPctField = document.getElementById('refugo_pct');
        const refugoPctFlexoField = document.getElementById('refugo_pct_flexo');
        const eficienciaPctField = document.getElementById('eficiencia_pct');
        const velocidadeUnMinField = document.getElementById('velocidade_un_min');
        const velocidadeUnMinFlexoField = document.getElementById('velocidade_un_min_flexo');
        const perdasUnField = document.getElementById('perdas_un_hidden');
        const tempoProdSField = document.getElementById('tempo_prod_s');
        const tempoAcertoSField = document.getElementById('tempo_acerto_s');
        
        if(refugoPctField) refugoPctField.value = actual_scrap_pct_sos.toFixed(2);
        if(refugoPctFlexoField) refugoPctFlexoField.value = actual_scrap_pct_flexo.toFixed(2);
        if(eficienciaPctField) eficienciaPctField.value = total_efficiency.toFixed(2);
        if(velocidadeUnMinField) velocidadeUnMinField.value = actual_speed_un_min.toFixed(2);
        if(velocidadeUnMinFlexoField) velocidadeUnMinFlexoField.value = actual_speed_un_min_flexo.toFixed(2);
        if(perdasUnField) perdasUnField.value = perdas_un.toFixed(0);
        if(tempoProdSField) tempoProdSField.value = actual_prod_time_s;
        if(tempoAcertoSField) tempoAcertoSField.value = actual_setup_time_s;
    }

    // Inicializa campos numéricos com valores padrão ao carregar a página
    document.querySelectorAll('input[type=number]').forEach(function(campo) {
        // Se o campo estiver vazio ou não tiver valor definido
        if (campo.value === '' || campo.value === null || campo.value === undefined) {
            // Campos float (com step decimal) recebem 0.0
            if (campo.step && parseFloat(campo.step) < 1) {
                campo.value = '0.0';
            } else {
                // Campos int recebem 0
                campo.value = '0';
            }
        }
    });
    
    function sincronizarObrigatoriedadeRoboAlca() {
        const qtdRobo = parseInt(document.getElementById('quantidade_robo').value, 10) || 0;
        const selectRobo = document.getElementById('robo_alca');
        if (!selectRobo) return;
        const obrigatorio = qtdRobo > 0;
        selectRobo.required = obrigatorio;
        selectRobo.style.borderColor = (obrigatorio && !selectRobo.value) ? 'red' : '';
    }

    function validarRoboAlcaNoEnvio(event) {
        const qtdRobo = parseInt(document.getElementById('quantidade_robo').value, 10) || 0;
        const selectRobo = document.getElementById('robo_alca');
        if (qtdRobo > 0 && selectRobo && !selectRobo.value) {
            event.preventDefault();
            selectRobo.required = true;
            selectRobo.style.borderColor = 'red';
            selectRobo.focus();
            alert('Se a Quantidade Robô for maior que zero, é obrigatório selecionar o Robô Alça.');
            return false;
        }
        return true;
    }

    document.querySelectorAll('input,select').forEach(el=>{el.addEventListener('change',calcPreview); el.addEventListener('change', validateMilheiro)});
    document.querySelectorAll('input[type=number]').forEach(el => el.addEventListener('input', calcPreview));
    const qtdRoboInput = document.getElementById('quantidade_robo');
    if (qtdRoboInput) {
        qtdRoboInput.addEventListener('input', sincronizarObrigatoriedadeRoboAlca);
        qtdRoboInput.addEventListener('change', sincronizarObrigatoriedadeRoboAlca);
    }
    const selectRoboAlca = document.getElementById('robo_alca');
    if (selectRoboAlca) {
        selectRoboAlca.addEventListener('change', sincronizarObrigatoriedadeRoboAlca);
    }
    const formLancamento = document.getElementById('form-lancamento');
    if (formLancamento) {
        formLancamento.addEventListener('submit', validarRoboAlcaNoEnvio);
    }
    setupExtraDayToggles(SOS_EXTRA_DAYS);
    setupExtraDayToggles(IMPRESSORA_EXTRA_DAYS);
    if(!document.getElementById('data').value){document.getElementById('data').value="{{ lancamento.data if lancamento else '' }}"||new Date().toISOString().split('T')[0];}
    showExtraDaysIfFilled(SOS_EXTRA_DAYS);
    showExtraDaysIfFilled(IMPRESSORA_EXTRA_DAYS);
    sincronizarObrigatoriedadeRoboAlca();
    calcPreview();
}); 