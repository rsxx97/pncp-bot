"""Gerador de declarações de habilitação — sem API.

Gera PDFs prontos para assinatura com dados da empresa preenchidos.
Templates padronizados conforme Lei 14.133/2021 e similares.
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from fpdf import FPDF

log = logging.getLogger("declaracao_builder")

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "empresa_habilitacao.json"
OUTPUT_DIR = BASE_DIR / "data" / "habilitacao"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _data_extenso() -> str:
    d = datetime.now()
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def load_empresa(key: str = "manutec") -> dict:
    """Carrega dados da empresa pelo key (config global — fallback/operador)."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for e in data["empresas"]:
        if e["key"] == key:
            return e
    return data["empresas"][0]


def empresa_from_tenant(emp: dict) -> dict:
    """Converte uma empresa do tenant (tabela tenant_empresas) no shape que as
    declarações esperam. Cada cliente gera com OS DADOS DELE, não da Manutec.

    Tolera campos faltando (string vazia) pra nunca quebrar a geração — os campos
    em branco aparecem vazios na declaração e o cliente completa no perfil.
    """
    def _as_dict(v):
        if isinstance(v, dict):
            return v
        if isinstance(v, str) and v.strip():
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    end = _as_dict(emp.get("endereco") or emp.get("endereco_json"))
    rep = _as_dict(emp.get("representante_legal") or emp.get("representante_legal_json"))
    return {
        "razao_social": emp.get("nome") or emp.get("razao_social") or "",
        "nome_fantasia": emp.get("nome_fantasia", ""),
        "cnpj": emp.get("cnpj") or "",
        "porte": emp.get("porte") or "ME",
        "endereco": {
            "logradouro": end.get("logradouro", ""),
            "numero": end.get("numero", ""),
            "complemento": end.get("complemento", ""),
            "bairro": end.get("bairro", ""),
            "cidade": end.get("cidade", ""),
            "uf": end.get("uf", ""),
            "cep": end.get("cep", ""),
        },
        "representante_legal": {
            "nome": rep.get("nome", ""),
            "cargo": rep.get("cargo", "Representante Legal"),
            "rg": rep.get("rg", ""),
            "orgao_emissor": rep.get("orgao_emissor", ""),
            "cpf": rep.get("cpf", ""),
            "nacionalidade": rep.get("nacionalidade", "brasileiro(a)"),
            "estado_civil": rep.get("estado_civil", ""),
        },
        "inscricao_estadual": emp.get("inscricao_estadual", ""),
        "inscricao_municipal": emp.get("inscricao_municipal", ""),
        "logo_path": emp.get("logo_path", ""),
    }


_FONTS_INITIALIZED = False
_FONT_NAME = "Helvetica"
# Logo da empresa em uso na geração corrente (setado por gerar_pacote_completo).
# Cada empresa tem o seu — assim a declaração sai com a marca do cliente logado.
_DEFAULT_LOGO = None


def _resolver_logo(logo_path):
    """Resolve o caminho do logo (absoluto ou relativo ao projeto). None se não existir."""
    if not logo_path:
        return None
    p = Path(logo_path)
    if not p.is_absolute():
        p = BASE_DIR / logo_path
    return str(p) if p.exists() else None

def _ensure_unicode_font(pdf: FPDF):
    """Tenta usar Arial (Windows) com Unicode, senão cai pra Helvetica."""
    global _FONT_NAME
    import platform
    if platform.system() == "Windows":
        try:
            pdf.add_font("Arial", "", "C:/Windows/Fonts/arial.ttf")
            pdf.add_font("Arial", "B", "C:/Windows/Fonts/arialbd.ttf")
            pdf.add_font("Arial", "I", "C:/Windows/Fonts/ariali.ttf")
            _FONT_NAME = "Arial"
        except Exception:
            _FONT_NAME = "Helvetica"


class DeclaracaoPDF(FPDF):
    """PDF customizado para declarações."""

    def __init__(self, titulo: str = "DECLARAÇÃO", logo_path: str = None):
        super().__init__()
        self.titulo = titulo
        self.logo_path = _resolver_logo(logo_path or _DEFAULT_LOGO)
        _ensure_unicode_font(self)
        self.font_name = _FONT_NAME
        self.set_auto_page_break(auto=True, margin=20)
        self.add_page()
        self.set_margins(25, 25, 25)

    def header(self):
        # Logo da empresa centralizado no topo (se houver).
        if self.logo_path:
            try:
                w = 38
                self.image(self.logo_path, x=(self.w - w) / 2, y=10, w=w)
                self.set_y(10 + w * 0.62 + 4)  # desce abaixo do logo
            except Exception:
                pass
        self.set_font(getattr(self, "font_name", "Helvetica"), "B", 14)
        self.cell(0, 10, self.titulo, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(getattr(self, "font_name", "Helvetica"), "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - Licitações AI",
                 align="C")

    def body(self, texto: str, fonte_size: int = 11):
        self.set_font(getattr(self, "font_name", "Helvetica"), "", fonte_size)
        self.set_text_color(0, 0, 0)
        # Multi-line com justificação
        self.multi_cell(0, 7, texto, align="J")
        self.ln(4)

    def assinatura(self, empresa: dict, edital_local: str = None):
        local = edital_local or f"{empresa['endereco']['cidade']}-{empresa['endereco']['uf']}"
        data = _data_extenso()
        self.ln(15)
        fn = getattr(self, "font_name", "Helvetica")
        self.set_font(fn, "", 11)
        self.cell(0, 6, f"{local}, {data}.", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(18)
        self.cell(0, 0, "_" * 55, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        rep = empresa["representante_legal"]
        self.cell(0, 5, rep["nome"], align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, rep["cargo"], align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"RG: {rep['rg']} ({rep['orgao_emissor']}) - CPF: {rep['cpf']}",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.set_font(fn, "B", 10)
        self.cell(0, 5, empresa["razao_social"], align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font(fn, "", 10)
        self.cell(0, 5, f"CNPJ: {empresa['cnpj']}", align="C", new_x="LMARGIN", new_y="NEXT")


# ----------------------------------------------------------------
# TEMPLATES DE DECLARAÇÕES
# ----------------------------------------------------------------

def _empresa_id_texto(empresa: dict) -> str:
    """Texto identificador da empresa para uso em declarações."""
    end = empresa["endereco"]
    return (
        f"{empresa['razao_social']}, pessoa jurídica de direito privado, "
        f"inscrita no CNPJ sob o nº {empresa['cnpj']}, "
        f"com sede à {end['logradouro']}, {end['numero']}"
        f"{', ' + end['complemento'] if end.get('complemento') else ''}, "
        f"{end['bairro']}, {end['cidade']}/{end['uf']}, CEP {end['cep']}, "
        f"neste ato representada por seu {empresa['representante_legal']['cargo'].lower()}, "
        f"{empresa['representante_legal']['nome']}, "
        f"{empresa['representante_legal']['nacionalidade']}, "
        f"{empresa['representante_legal']['estado_civil']}, "
        f"portador do RG nº {empresa['representante_legal']['rg']} "
        f"e inscrito no CPF sob o nº {empresa['representante_legal']['cpf']}"
    )


def gerar_nao_emprega_menor(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de que não emprega menor (CLT art. 7º, XXXIII)."""
    pdf = DeclaracaoPDF("DECLARAÇÃO — NÃO EMPREGA MENOR")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, para fins do disposto no "
        f"inciso XXXIII do art. 7º da Constituição Federal, no inciso V do art. 68 da Lei nº 14.133/2021, "
        f"que NÃO emprega menor de 18 (dezoito) anos em trabalho noturno, perigoso ou insalubre, "
        f"e NÃO emprega menor de 16 (dezesseis) anos, salvo na condição de aprendiz, "
        f"a partir dos 14 (quatorze) anos.\n\n"
        f"Por ser a expressão da verdade, firma a presente declaração."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "01_nao_emprega_menor.pdf"
    pdf.output(str(output))
    return output


def gerar_me_epp(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de enquadramento como ME/EPP (LC 123/2006)."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE ENQUADRAMENTO - ME/EPP")
    porte = empresa.get("porte", "ME")
    porte_desc = "Microempresa - ME" if porte == "ME" else "Empresa de Pequeno Porte - EPP"
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, sob as penas da lei, "
        f"para fins do disposto na Lei Complementar nº 123/2006 e na Lei nº 14.133/2021, "
        f"que se enquadra como {porte_desc}, cumprindo os requisitos do art. 3º da LC 123/2006, "
        f"inexistindo quaisquer das situações impeditivas dispostas no § 4º do mesmo artigo.\n\n"
        f"DECLARA ainda ter ciência do direito de preferência e tratamento diferenciado "
        f"previstos nos arts. 42 a 49 da LC 123/2006."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "02_me_epp.pdf"
    pdf.output(str(output))
    return output


def gerar_fatos_impeditivos(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de inexistência de fatos impeditivos."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE INEXISTÊNCIA DE FATOS IMPEDITIVOS")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, sob as penas da lei, "
        f"que até a presente data INEXISTEM fatos impeditivos de habilitação em "
        f"procedimentos licitatórios, estando ciente da obrigatoriedade de declarar "
        f"ocorrências posteriores.\n\n"
        f"DECLARA ainda que não foi declarada inidônea por ato do Poder Público "
        f"e nem está suspensa do direito de licitar ou contratar com a Administração Pública, "
        f"bem como não está cumprindo penalidade imposta pela Lei nº 14.133/2021, "
        f"Lei nº 12.846/2013 (Lei Anticorrupção) ou qualquer outra que a impeça, "
        f"direta ou indiretamente, de participar desta licitação."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "03_fatos_impeditivos.pdf"
    pdf.output(str(output))
    return output


def gerar_independencia_proposta(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de elaboração independente de proposta."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE ELABORAÇÃO INDEPENDENTE DE PROPOSTA")
    ed_num = (edital_info or {}).get("numero") or (edital_info or {}).get("pncp_id", "")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA que a proposta apresentada "
        f"para a licitação {ed_num} foi elaborada de maneira independente, "
        f"e que o conteúdo da mesma não foi, no todo ou em parte, direta ou indiretamente, "
        f"informado, discutido ou recebido de qualquer outro participante potencial ou "
        f"de fato, por qualquer meio ou por qualquer pessoa.\n\n"
        f"DECLARA que a intenção de apresentar a proposta não foi informada, "
        f"discutida ou recebida de qualquer outro participante potencial ou de fato, "
        f"por qualquer meio ou por qualquer pessoa.\n\n"
        f"DECLARA que não tentou, por qualquer meio ou por qualquer pessoa, "
        f"influir na decisão de qualquer outro participante potencial ou de fato."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "04_independencia_proposta.pdf"
    pdf.output(str(output))
    return output


def gerar_pleno_conhecimento(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de pleno conhecimento do edital."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE PLENO CONHECIMENTO DO EDITAL")
    ed_num = (edital_info or {}).get("numero") or (edital_info or {}).get("pncp_id", "")
    orgao = (edital_info or {}).get("orgao", "")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA ter pleno conhecimento "
        f"e aceitar todos os termos, condições e exigências do edital "
        f"{ed_num}{' do órgão ' + orgao if orgao else ''} e seus anexos, "
        f"concordando integralmente com suas cláusulas e obrigações.\n\n"
        f"DECLARA ainda que obteve todas as informações necessárias para apresentação "
        f"da proposta e que os valores ofertados cobrem integralmente todos os custos "
        f"diretos e indiretos, impostos, taxas, encargos trabalhistas, previdenciários, "
        f"fiscais e comerciais, tributos, transportes, seguros e quaisquer outros "
        f"que incidam ou venham a incidir sobre o objeto da licitação."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "05_pleno_conhecimento.pdf"
    pdf.output(str(output))
    return output


def gerar_dispensa_visita(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de dispensa de visita técnica."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE DISPENSA DE VISITA TÉCNICA")
    ed_num = (edital_info or {}).get("numero") or (edital_info or {}).get("pncp_id", "")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, para os fins do Edital "
        f"{ed_num}, que OPTA por NÃO realizar a visita técnica facultativa ao(s) "
        f"local(is) de execução dos serviços, declarando ter conhecimento pleno "
        f"das condições locais e peculiaridades inerentes à natureza dos trabalhos, "
        f"assumindo TOTAL RESPONSABILIDADE por tal fato e não utilizará desse feito "
        f"para quaisquer questionamentos futuros que ensejarem avenças técnicas ou "
        f"financeiras com o Contratante."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "06_dispensa_visita.pdf"
    pdf.output(str(output))
    return output


def gerar_idoneidade(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de idoneidade."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE IDONEIDADE")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, sob as penas da lei, "
        f"NÃO ter sido declarada inidônea para licitar ou contratar com "
        f"a Administração Pública Federal, Estadual, Distrital ou Municipal, "
        f"nem constar em qualquer cadastro de impedimento (CEIS, CNEP, CADIN, "
        f"Cadastro Nacional de Empresas Punidas ou equivalentes).\n\n"
        f"DECLARA ainda que não está cumprindo nenhuma sanção administrativa "
        f"que impeça sua participação em licitações ou contratações com o Poder Público."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "07_idoneidade.pdf"
    pdf.output(str(output))
    return output


def gerar_cumprimento_requisitos(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de cumprimento de requisitos de habilitação."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE CUMPRIMENTO DOS REQUISITOS DE HABILITAÇÃO")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, sob as penas da lei, "
        f"nos termos do art. 63, I da Lei nº 14.133/2021, que CUMPRE plenamente "
        f"todos os requisitos de habilitação exigidos no edital e seus anexos.\n\n"
        f"DECLARA estar ciente de que a falsidade desta declaração configura "
        f"crime previsto no art. 299 do Código Penal, sujeitando o declarante às "
        f"penalidades legais cabíveis."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "08_cumprimento_requisitos.pdf"
    pdf.output(str(output))
    return output


def gerar_nepotismo(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de inexistência de nepotismo."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE INEXISTÊNCIA DE NEPOTISMO")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, para os devidos fins, "
        f"que NÃO possui em seu quadro societário, de administração ou empregados "
        f"pessoas que sejam cônjuges, companheiros ou parentes em linha reta, "
        f"colateral ou por afinidade, até o terceiro grau, de agentes públicos "
        f"que exerçam cargo em comissão ou função de confiança no órgão contratante, "
        f"vedando assim o nepotismo nos termos da Súmula Vinculante nº 13 do STF."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "09_nepotismo.pdf"
    pdf.output(str(output))
    return output


def gerar_lgpd(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de cumprimento da LGPD."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE CUMPRIMENTO DA LGPD")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, para os fins desta licitação, "
        f"que adota políticas e procedimentos em conformidade com a Lei Geral de "
        f"Proteção de Dados Pessoais — Lei nº 13.709/2018 (LGPD), e seus regulamentos, "
        f"comprometendo-se a tratar quaisquer dados pessoais obtidos em decorrência "
        f"da presente contratação com o devido respeito aos princípios de finalidade, "
        f"adequação, necessidade, segurança, prevenção, não discriminação e transparência."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "10_lgpd.pdf"
    pdf.output(str(output))
    return output


def gerar_reserva_cargos_pcd(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de reserva de cargos para PCD (Lei 14.133/2021, art. 63, IV)."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE RESERVA DE CARGOS - PCD E REABILITADOS")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, sob as penas da lei, "
        f"em atendimento ao disposto no art. 63, inciso IV da Lei nº 14.133/2021, "
        f"que cumpre as exigências de reserva de cargos prevista em lei para pessoa "
        f"com deficiência (Lei nº 8.213/1991) ou para reabilitado da Previdência Social "
        f"e que atende às regras de acessibilidade previstas na legislação."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "11_reserva_pcd.pdf"
    pdf.output(str(output))
    return output


def gerar_nao_utilizacao_trabalho_degradante(empresa: dict, edital_info: dict = None, output: Path = None) -> Path:
    """Declaração de não utilização de mão de obra degradante ou escrava."""
    pdf = DeclaracaoPDF("DECLARAÇÃO DE NÃO UTILIZAÇÃO DE MÃO DE OBRA DEGRADANTE")
    texto = (
        f"{_empresa_id_texto(empresa)}, DECLARA, sob as penas da lei, "
        f"que NÃO se utiliza de mão de obra direta ou indireta análoga a de escravo, "
        f"trabalho infantil ou trabalho em condições degradantes, conforme o disposto "
        f"no art. 149 do Código Penal, e que cumpre rigorosamente as normas de "
        f"segurança, saúde e higiene do trabalho, em conformidade com as Normas "
        f"Regulamentadoras do Ministério do Trabalho e Emprego."
    )
    pdf.body(texto)
    pdf.assinatura(empresa)
    output = output or OUTPUT_DIR / "12_trabalho_digno.pdf"
    pdf.output(str(output))
    return output


# ----------------------------------------------------------------
# Gerador de pacote completo
# ----------------------------------------------------------------

TIPOS_DISPONIVEIS = {
    "nao_emprega_menor": {"nome": "Não Emprega Menor", "func": gerar_nao_emprega_menor, "ordem": 1},
    "me_epp": {"nome": "ME/EPP", "func": gerar_me_epp, "ordem": 2},
    "fatos_impeditivos": {"nome": "Inexistência de Fatos Impeditivos", "func": gerar_fatos_impeditivos, "ordem": 3},
    "independencia_proposta": {"nome": "Elaboração Independente de Proposta", "func": gerar_independencia_proposta, "ordem": 4},
    "pleno_conhecimento": {"nome": "Pleno Conhecimento do Edital", "func": gerar_pleno_conhecimento, "ordem": 5},
    "dispensa_visita": {"nome": "Dispensa de Visita Técnica", "func": gerar_dispensa_visita, "ordem": 6},
    "idoneidade": {"nome": "Idoneidade", "func": gerar_idoneidade, "ordem": 7},
    "cumprimento_requisitos": {"nome": "Cumprimento de Requisitos de Habilitação", "func": gerar_cumprimento_requisitos, "ordem": 8},
    "nepotismo": {"nome": "Inexistência de Nepotismo", "func": gerar_nepotismo, "ordem": 9},
    "lgpd": {"nome": "Cumprimento da LGPD", "func": gerar_lgpd, "ordem": 10},
    "reserva_pcd": {"nome": "Reserva de Cargos PCD", "func": gerar_reserva_cargos_pcd, "ordem": 11},
    "trabalho_digno": {"nome": "Não Utilização de Trabalho Degradante", "func": gerar_nao_utilizacao_trabalho_degradante, "ordem": 12},
}


def gerar_pacote_completo(
    edital_info: dict,
    empresa_key: str = "manutec",
    tipos: list[str] = None,
    empresa: dict = None,
) -> Path:
    """Gera pacote ZIP com todas as declarações preenchidas para um edital.

    `empresa` (dict já no shape do gerador) tem precedência — é o caminho
    multi-tenant: cada cliente gera com OS DADOS DELE. Sem ele, cai no config
    global por `empresa_key` (operador/legado).
    """
    import zipfile

    if empresa is None:
        empresa = load_empresa(empresa_key)
    tipos = tipos or list(TIPOS_DISPONIVEIS.keys())

    # Logo da empresa logada (cai pra None se não tiver — declaração sai sem marca).
    global _DEFAULT_LOGO
    _DEFAULT_LOGO = empresa.get("logo_path")

    pncp_id = edital_info.get("pncp_id", "edital")
    safe_id = pncp_id.replace("/", "_").replace("-", "_")

    pasta_edital = OUTPUT_DIR / safe_id
    pasta_edital.mkdir(parents=True, exist_ok=True)

    arquivos_gerados = []
    for tipo_key in tipos:
        if tipo_key not in TIPOS_DISPONIVEIS:
            continue
        info = TIPOS_DISPONIVEIS[tipo_key]
        ordem = str(info["ordem"]).zfill(2)
        nome_arquivo = f"{ordem}_{tipo_key}.pdf"
        output_path = pasta_edital / nome_arquivo
        try:
            info["func"](empresa, edital_info, output_path)
            arquivos_gerados.append(output_path)
            log.info(f"  + {info['nome']}: {output_path.name}")
        except Exception as e:
            log.error(f"  Erro gerando {tipo_key}: {e}")

    # Gera ZIP
    zip_path = pasta_edital / f"pacote_habilitacao_{safe_id}.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for arq in arquivos_gerados:
            zf.write(str(arq), arq.name)

    log.info(f"Pacote completo: {zip_path} ({len(arquivos_gerados)} declarações)")
    _DEFAULT_LOGO = None
    return zip_path


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Teste com edital mock
    mock = {
        "pncp_id": "12345678000190-2026-99",
        "orgao": "Tribunal de Justiça - Teste",
        "numero": "PE-001/2026",
    }
    zip_path = gerar_pacote_completo(mock)
    print(f"\nPacote gerado: {zip_path}")
