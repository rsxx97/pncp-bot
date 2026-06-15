"""Envio de e-mail transacional via Resend (https://resend.com)."""
import logging
import httpx

from config.settings import RESEND_API_KEY, RESEND_FROM, APP_BASE_URL

log = logging.getLogger("email")

_API = "https://api.resend.com/emails"


def enviar_email(to: str, subject: str, html: str) -> bool:
    """Envia um e-mail. Retorna True se aceito pelo Resend, False caso contrário.
    Nunca levanta exceção — falha de e-mail não pode derrubar o cadastro."""
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY ausente — e-mail não enviado (%s)", subject)
        return False
    try:
        r = httpx.post(
            _API,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": RESEND_FROM, "to": [to], "subject": subject, "html": html},
            timeout=20,
        )
        if r.status_code == 200:
            return True
        log.error("Resend %s: %s", r.status_code, r.text[:300])
        return False
    except Exception as e:  # noqa: BLE001
        log.error("Falha enviando e-mail: %s", e)
        return False


def enviar_confirmacao(to: str, nome: str, link: str) -> bool:
    return enviar_email(to, "Confirme seu e-mail · LicitaçõesAI", _confirmacao_html(nome or "", link))


# ── Templates ────────────────────────────────────────────────────────────

def _wrap(inner: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#F1F5F9;font-family:Segoe UI,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F1F5F9;padding:32px 0">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(2,6,23,.08)">
<tr><td style="background:linear-gradient(135deg,#0B1220,#111A2B);padding:24px 32px">
<span style="color:#fff;font-size:18px;font-weight:800">Licitações<span style="color:#34D399">AI</span></span>
</td></tr>
<tr><td style="padding:32px">{inner}</td></tr>
<tr><td style="padding:18px 32px;background:#F8FAFC;color:#94A3B8;font-size:12px;text-align:center">
Licitações AI · Monitoramento de licitações públicas · Dados do PNCP</td></tr>
</table></td></tr></table></body></html>"""


def _confirmacao_html(nome: str, link: str) -> str:
    saudacao = f"Olá, {nome}!" if nome else "Olá!"
    inner = f"""
<h1 style="font-size:21px;color:#0B1220;margin:0 0 12px">{saudacao}</h1>
<p style="font-size:15px;color:#475569;line-height:1.6;margin:0 0 24px">
Falta só um passo para ativar sua conta no <b>LicitaçõesAI</b>. Confirme seu e-mail clicando no botão abaixo:</p>
<table cellpadding="0" cellspacing="0" style="margin:0 0 24px"><tr><td style="border-radius:11px;background:linear-gradient(135deg,#10B981,#34D399)">
<a href="{link}" style="display:inline-block;padding:13px 30px;color:#06281E;font-size:15px;font-weight:800;text-decoration:none">Confirmar meu e-mail</a>
</td></tr></table>
<p style="font-size:13px;color:#94A3B8;line-height:1.6;margin:0">
Se o botão não funcionar, copie e cole este link no navegador:<br>
<a href="{link}" style="color:#10B981;word-break:break-all">{link}</a></p>
<p style="font-size:12px;color:#CBD5E1;margin:20px 0 0">Se você não criou esta conta, ignore este e-mail.</p>"""
    return _wrap(inner)


def pagina_confirmacao_html(ok: bool, nome: str = "") -> str:
    """Página HTML mostrada quando o usuário clica no link de confirmação."""
    if ok:
        titulo, cor, msg = "E-mail confirmado! ✓", "#10B981", "Sua conta está ativa. Pode voltar ao app e aproveitar."
        botao = f'<a href="{APP_BASE_URL}" style="display:inline-block;margin-top:8px;padding:13px 30px;border-radius:11px;background:linear-gradient(135deg,#10B981,#34D399);color:#06281E;font-weight:800;text-decoration:none">Ir para o app</a>'
    else:
        titulo, cor, msg = "Link inválido ou expirado", "#EF4444", "Este link de confirmação não é válido. Faça login e reenvie a confirmação."
        botao = f'<a href="{APP_BASE_URL}" style="display:inline-block;margin-top:8px;padding:13px 30px;border-radius:11px;background:#0B1220;color:#fff;font-weight:700;text-decoration:none">Voltar ao app</a>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#F1F5F9;font-family:Segoe UI,Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center">
<div style="background:#fff;border-radius:16px;padding:40px;max-width:420px;text-align:center;box-shadow:0 12px 40px rgba(2,6,23,.1)">
<div style="font-size:18px;font-weight:800;color:#0B1220;margin-bottom:18px">Licitações<span style="color:#34D399">AI</span></div>
<h1 style="font-size:22px;color:{cor};margin:0 0 10px">{titulo}</h1>
<p style="font-size:15px;color:#475569;line-height:1.6;margin:0 0 18px">{msg}</p>
{botao}</div></body></html>"""
