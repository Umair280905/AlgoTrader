"""
Management command: python manage.py kotak_login

Runs the Kotak Neo OTP login flow and prints the access token to copy
into your .env file as KOTAK_ACCESS_TOKEN.

Run this once each morning before starting live trading.
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Authenticate with Kotak Neo and obtain a fresh access token.'

    def handle(self, *args, **options):
        try:
            from neo_api_client import NeoAPI
        except ImportError:
            raise CommandError("neo-api-client is not installed. Run: pip install neo-api-client")

        for attr in ('KOTAK_CONSUMER_KEY', 'KOTAK_CONSUMER_SECRET', 'KOTAK_NEO_FIN_KEY'):
            if not getattr(settings, attr, ''):
                raise CommandError(f"{attr} is not set in settings / .env")

        client = NeoAPI(
            consumer_key=settings.KOTAK_CONSUMER_KEY,
            consumer_secret=settings.KOTAK_CONSUMER_SECRET,
            environment='prod',
            access_token=None,
            neo_fin_key=settings.KOTAK_NEO_FIN_KEY,
        )

        mobile = settings.KOTAK_MOBILE or input("Mobile number: ")
        password = settings.KOTAK_PASSWORD or input("Trading password: ")

        self.stdout.write("Sending OTP to your registered mobile/email…")
        resp = client.login(mobilenumber=mobile, password=password)
        self.stdout.write(str(resp))

        otp = input("Enter OTP: ").strip()
        session_resp = client.session_2fa(OTP=otp)
        self.stdout.write(str(session_resp))

        token = None
        if isinstance(session_resp, dict):
            token = (
                session_resp.get('data', {}).get('token')
                or session_resp.get('token')
                or session_resp.get('access_token')
            )

        if token:
            self.stdout.write(self.style.SUCCESS(f"\nAccess token obtained successfully."))
            self.stdout.write(f"\nAdd this line to your .env file:\n")
            self.stdout.write(self.style.WARNING(f"KOTAK_ACCESS_TOKEN={token}"))
        else:
            self.stdout.write(self.style.WARNING(
                "\nCould not extract token automatically. Full response above — "
                "find the token field and set KOTAK_ACCESS_TOKEN in your .env."
            ))
