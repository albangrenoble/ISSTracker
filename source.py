#!/usr/bin/env python3
"""
ISS Tracker - France
====================
Surveille la position de l'ISS en temps réel et envoie un email
lorsqu'elle passe au-dessus de la France métropolitaine.

Utilisation :
    1. Renseigne tes identifiants Gmail dans le fichier .env (voir plus bas)
    2. pip install requests python-dotenv
    3. python iss_tracker.py

Configuration Gmail :
    - Va sur https://myaccount.google.com/apppasswords
    - Crée un "Mot de passe d'application" pour "Mail"
    - Utilise ce mot de passe (16 caractères) dans GMAIL_APP_PASSWORD
"""

import json
import logging
import os
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Essaie de charger un fichier .env s'il existe (optionnel)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Email ---
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "ton.email@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "xxxx xxxx xxxx xxxx")
DESTINATAIRE = os.getenv("DESTINATAIRE", GMAIL_ADDRESS)  # par défaut, s'envoie à soi-même

# --- Tracking ---
INTERVALLE_VERIFICATION = 30       # secondes entre chaque vérification
COOLDOWN_NOTIFICATION = 90 * 60    # 90 minutes entre deux notifications (un passage dure ~10 min)

# --- Bounding box de la France métropolitaine (approximation) ---
FRANCE_LAT_MIN = 69    # Sud (Corse / Perpignan)
FRANCE_LAT_MAX = 51.1    # Nord (Dunkerque)
FRANCE_LON_MIN = -5.2    # Ouest (Brest)
FRANCE_LON_MAX = 9.6     # Est (Strasbourg / Corse)

# --- API ---
ISS_API_URL = "http://api.open-notify.org/iss-now.json"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("iss_tracker")


# ---------------------------------------------------------------------------
# Fonctions
# ---------------------------------------------------------------------------

def get_iss_position() -> tuple[float, float] | None:
    """Récupère la position actuelle de l'ISS (latitude, longitude)."""
    # {"iss_position": {"latitude": "-1.2956", "longitude": "26.8140"}, "timestamp": 1773326355, "message": "success"}
    try:
        response = requests.get(ISS_API_URL, timeout=10)
        response.raise_for_status()  # cas erreur http 
        data = response.json() # parse en un dictionnair json -> dic 

        lat = float(data["iss_position"]["latitude"])
        lon = float(data["iss_position"]["longitude"])
        return lat, lon

    except (requests.RequestException, KeyError, ValueError) as e:
        log.warning(f"Erreur lors de la récupération de la position ISS : {e}")
        return None


def est_au_dessus_de_la_france(lat: float, lon: float) -> bool:
    """Vérifie si les coordonnées sont dans la bounding box de la France."""
    return (
        FRANCE_LAT_MIN <= lat <= FRANCE_LAT_MAX
        and FRANCE_LON_MIN <= lon <= FRANCE_LON_MAX
    )


def envoyer_email(lat: float, lon: float):
    """Envoie un email de notification avec la position de l'ISS."""
    maintenant = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")

    sujet = "🛰️ L'ISS passe au-dessus de la France !"

    corps_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); color: white;
                    padding: 30px; border-radius: 12px; text-align: center;">
            <h1 style="margin: 0;">🛰️ ISS au-dessus de la France !</h1>
            <p style="font-size: 18px; opacity: 0.9;">{maintenant}</p>
        </div>

        <div style="padding: 20px; background: #f8f9fa; border-radius: 0 0 12px 12px;">
            <h2>📍 Position actuelle</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Latitude</td>
                    <td style="padding: 8px;">{lat:.4f}°</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Longitude</td>
                    <td style="padding: 8px;">{lon:.4f}°</td>
                </tr>
            </table>

            <p style="margin-top: 20px;">
                🔭 <strong>Regarde le ciel !</strong> L'ISS est visible à l'œil nu
                comme une étoile brillante qui se déplace sans clignoter.
            </p>

            <p style="margin-top: 15px;">
                📍 <a href="https://www.google.com/maps?q={lat},{lon}" target="_blank">
                    Voir sur Google Maps
                </a>
                &nbsp;|&nbsp;
                🌍 <a href="https://spotthestation.nasa.gov/" target="_blank">
                    Spot The Station (NASA)
                </a>
            </p>
        </div>
    </body>
    </html>
    """

    corps_texte = (
        f"L'ISS passe au-dessus de la France !\n"
        f"Date : {maintenant}\n"
        f"Position : {lat:.4f}°N, {lon:.4f}°E\n"
        f"Google Maps : https://www.google.com/maps?q={lat},{lon}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = DESTINATAIRE
    msg.attach(MIMEText(corps_texte, "plain"))
    msg.attach(MIMEText(corps_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
            serveur.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            serveur.send_message(msg)
        log.info(f"✅ Email envoyé à {DESTINATAIRE}")
    except smtplib.SMTPException as e:
        log.error(f"❌ Erreur d'envoi email : {e}")


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 60)
    log.info("🛰️  ISS Tracker - France")
    log.info(f"   Vérification toutes les {INTERVALLE_VERIFICATION}s")
    log.info(f"   Cooldown entre notifications : {COOLDOWN_NOTIFICATION // 60} min")
    log.info(f"   Notifications envoyées à : {DESTINATAIRE}")
    log.info("=" * 60)

    derniere_notification = None

    while True:
        position = get_iss_position()

        if position is None:
            log.info("⏳ Nouvelle tentative dans 60s...")
            time.sleep(60)
            continue

        lat, lon = position

        if est_au_dessus_de_la_france(lat, lon):
            log.info(f"🇫🇷 ISS AU-DESSUS DE LA FRANCE ! ({lat:.2f}°, {lon:.2f}°)")

            # Vérifier le cooldown
            maintenant = datetime.now()
            if (
                derniere_notification is None
                or maintenant - derniere_notification > timedelta(seconds=COOLDOWN_NOTIFICATION)
            ):
                envoyer_email(lat, lon)
                derniere_notification = maintenant
            else:
                restant = (
                    derniere_notification
                    + timedelta(seconds=COOLDOWN_NOTIFICATION)
                    - maintenant
                )
                log.info(f"⏸️  Cooldown actif, prochain email possible dans {restant}")
        else:
            log.info(f"🌍 ISS hors de France ({lat:.2f}°, {lon:.2f}°)")

        time.sleep(INTERVALLE_VERIFICATION)


if __name__ == "__main__":
    main()