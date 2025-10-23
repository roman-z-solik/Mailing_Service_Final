
from django.core.management.base import BaseCommand

from mailing.models import Mailing


class Command(BaseCommand):
    help = "Запускает обработку активных рассылок"

    def handle(self, *args, **options):
        self.stdout.write("Запуск обработки активных рассылок...")

        active_mailings = Mailing.objects.filter(status="Запущена")
        results = []

        for mailing in active_mailings:
            successful, failed = mailing.send_to_clients()
            results.append(
                {"mailing": mailing, "successful": successful, "failed": failed}
            )

        if results:
            for result in results:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Рассылка '{result['mailing']}': "
                        f"успешно - {result['successful']}, "
                        f"неудачно - {result['failed']}"
                    )
                )
        else:
            self.stdout.write("Активных рассылок не найдено")
