"""
Email notifications for new listings.

Requires env vars (or Streamlit secrets):
  GMAIL_USER         — your Gmail address
  GMAIL_APP_PASSWORD — Gmail App Password (not your main password)
  NOTIFY_EMAIL       — recipient address(es), comma-separated for multiple
                       e.g. "jan@gmail.com,anna@gmail.com"
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd


def _get_cfg():
    cfg = {
        "user":     os.environ.get("GMAIL_USER", ""),
        "password": os.environ.get("GMAIL_APP_PASSWORD", ""),
        "to":       os.environ.get("NOTIFY_EMAIL", ""),
    }
    if not all(cfg.values()):
        try:
            import streamlit as st
            cfg["user"]     = cfg["user"]     or st.secrets.get("GMAIL_USER", "")
            cfg["password"] = cfg["password"] or st.secrets.get("GMAIL_APP_PASSWORD", "")
            cfg["to"]       = cfg["to"]       or st.secrets.get("NOTIFY_EMAIL", "")
        except Exception:
            pass
    return cfg


def _build_html(new_df: pd.DataFrame) -> str:
    rows_html = ""
    for _, r in new_df.iterrows():
        cena = (
            f"{int(r['cena_pln']):,} PLN".replace(",", " ")
            if pd.notna(r.get("cena_pln")) else "—"
        )
        pow_ = (
            f"{int(r['powierzchnia_m2'])} m²"
            if pd.notna(r.get("powierzchnia_m2")) else "—"
        )
        rows_html += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee">
            <a href="{r.get('url','')}" style="color:#1565C0;font-weight:600">
              {str(r.get('tytul',''))[:70]}
            </a><br>
            <span style="font-size:12px;color:#666">
              📍 {r.get('miejscowosc','')} &nbsp;·&nbsp;
              {r.get('zrodlo','')} &nbsp;·&nbsp;
              {r.get('odcinek','')}
            </span>
          </td>
          <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">
            <b>{cena}</b>
          </td>
          <td style="padding:8px;border-bottom:1px solid #eee;white-space:nowrap">
            {pow_}
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:sans-serif;color:#222;max-width:700px;margin:auto">
      <h2 style="color:#1565C0">🌊 Nowe działki nad Liwcem</h2>
      <p>Znaleziono <b>{len(new_df)}</b> nowych ogłoszeń od ostatniego sprawdzenia.</p>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#e3f2fd">
            <th style="padding:8px;text-align:left">Ogłoszenie</th>
            <th style="padding:8px;text-align:left">Cena</th>
            <th style="padding:8px;text-align:left">Pow.</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="font-size:12px;color:#999;margin-top:24px">
        Wygenerowano automatycznie przez aplikację Działki nad Liwcem.
      </p>
    </body></html>"""


def send_new_listings(new_df: pd.DataFrame) -> bool:
    """
    Send email digest of new listings.
    Returns True on success, False if config missing or send failed.
    """
    if new_df.empty:
        return True

    cfg = _get_cfg()
    if not all(cfg.values()):
        return False

    # Support comma-separated list of recipients
    recipients = [a.strip() for a in cfg["to"].split(",") if a.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌊 {len(new_df)} nowych działek nad Liwcem"
    msg["From"]    = cfg["user"]
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(_build_html(new_df), "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(cfg["user"], cfg["password"])
            smtp.sendmail(cfg["user"], recipients, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def email_configured() -> bool:
    cfg = _get_cfg()
    return all(cfg.values())
