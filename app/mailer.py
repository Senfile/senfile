"""
Module dédié à l'envoi d'emails transactionnels : réinitialisation de mot
de passe, invitations à collaborer. Un seul point d'entrée SMTP, configuré
via les variables d'environnement SMTP_* (voir config.py).

En développement (SMTP_HOST vide), les emails ne sont pas envoyés mais
journalisés dans la console — pratique pour tester le flux sans vrai
serveur SMTP, sans jamais faire planter l'application.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import settings


def _send(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    if not settings.smtp_host:
        print(
            f"[mailer] SMTP non configuré — email non envoyé.\n"
            f"  À: {to_email}\n  Sujet: {subject}\n  Contenu: {text_body}\n"
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to_email], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001 — on ne veut jamais faire échouer la requête HTTP pour un souci SMTP
        print(f"[mailer] Échec de l'envoi à {to_email} : {exc}")
        return False


def _branded_html(title: str, body_text: str, cta_label: str, cta_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f3f2ef;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f2ef;padding:40px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;">
        <tr><td style="padding:32px 40px 8px;">
          <div style="font-family:Georgia,serif;font-size:20px;font-weight:600;color:#1c1b22;">Atelier</div>
        </td></tr>
        <tr><td style="padding:16px 40px 8px;">
          <h1 style="font-family:Georgia,serif;font-size:22px;color:#1c1b22;margin:0 0 12px;">{title}</h1>
          <div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#4a4852;">{body_text}</div>
        </td></tr>
        <tr><td style="padding:24px 40px 12px;">
          <a href="{cta_url}" style="display:inline-block;background:#4b3f72;color:#ffffff;text-decoration:none;
             font-family:Arial,sans-serif;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;">
            {cta_label}
          </a>
        </td></tr>
        <tr><td style="padding:8px 40px 32px;">
          <div style="font-family:Arial,sans-serif;font-size:11.5px;color:#8a8790;word-break:break-all;">
            Ou copiez ce lien : {cta_url}
          </div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    html = _branded_html(
        "Réinitialisez votre mot de passe",
        "Vous avez demandé la réinitialisation de votre mot de passe. "
        "Ce lien est valable une heure. Si vous n'êtes pas à l'origine de "
        "cette demande, vous pouvez ignorer cet email en toute sécurité.",
        "Choisir un nouveau mot de passe",
        reset_url,
    )
    text = f"Réinitialisez votre mot de passe (valable 1 heure) : {reset_url}"
    return _send(to_email, "Réinitialisation de votre mot de passe — Atelier", html, text)


def send_invite_email(to_email: str, inviter_name: str, document_title: str, invite_url: str, role: str) -> bool:
    role_label = "éditeur" if role == "editor" else "lecteur"
    html = _branded_html(
        f"{inviter_name} vous invite à collaborer",
        f"{inviter_name} vous invite à rejoindre « {document_title} » en tant que {role_label}.",
        "Rejoindre le document",
        invite_url,
    )
    text = f"{inviter_name} vous invite à rejoindre « {document_title} » : {invite_url}"
    return _send(to_email, f"Invitation à collaborer sur « {document_title} »", html, text)
