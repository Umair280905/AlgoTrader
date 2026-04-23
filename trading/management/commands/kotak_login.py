"""
Management command: python manage.py kotak_login

Runs the Kotak Neo v2 TOTP login flow and prints the access token to copy
into your .env file as KOTAK_ACCESS_TOKEN.

Prerequisites:
  - Register TOTP on https://www.kotaksecurities.com (Settings > TOTP)
  - Install Google Authenticator and scan the QR code

Run this once each morning before starting live trading.
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Authenticate with Kotak Neo v2 (TOTP) and obtain a fresh access token.'

    def handle(self, *args, **options):
        try:
            from neo_api_client import NeoAPI
        except ImportError:
            raise CommandError(
                "neo-api-client v2 is not installed. Run: "
                "pip install git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git@v2.0.1"
            )

        for attr in ('KOTAK_CONSUMER_KEY',):
            if not getattr(settings, attr, ''):
                raise CommandError(f"{attr} is not set in settings / .env")

        client = NeoAPI(
            consumer_key=settings.KOTAK_CONSUMER_KEY,
            environment='prod',
            access_token=None,
            neo_fin_key=settings.KOTAK_NEO_FIN_KEY or None,
        )

        mobile = settings.KOTAK_MOBILE or input("Mobile number (with country code, e.g. +919999999999): ")
        ucc    = settings.KOTAK_UCC    or input("UCC (Unique Client Code, e.g. AB123): ")
        totp   = input("Enter 6-digit TOTP from Google Authenticator: ").strip()

        self.stdout.write("Sending TOTP login request…")
        try:
            resp = client.totp_login(mobilenumber=mobile, ucc=ucc, totp=totp)
        except Exception as exc:
            raise CommandError(f"totp_login failed: {exc}") from exc
        self.stdout.write(str(resp))

        mpin = settings.KOTAK_MPIN or input("Enter MPIN: ").strip()

        self.stdout.write("Validating MPIN…")
        try:
            session_resp = client.totp_validate(mpin=mpin)
        except Exception as exc:
            raise CommandError(f"totp_validate failed: {exc}") from exc
        self.stdout.write(str(session_resp))

        token = None
        if isinstance(session_resp, dict):
            token = (
                session_resp.get('data', {}).get('token')
                or session_resp.get('token')
                or session_resp.get('access_token')
            )

        if token:
            self.stdout.write(self.style.SUCCESS("\nAccess token obtained successfully."))
            self.stdout.write("\nAdd this line to your .env file:\n")
            self.stdout.write(self.style.WARNING(f"KOTAK_ACCESS_TOKEN={token}"))
        else:
            self.stdout.write(self.style.WARNING(
                "\nCould not extract token automatically. Full response above — "
                "find the token field and set KOTAK_ACCESS_TOKEN in your .env."
            ))
