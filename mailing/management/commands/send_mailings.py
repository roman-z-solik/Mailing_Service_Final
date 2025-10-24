from django.core.management.base import BaseCommand

from mailing.models import Mailing, MailingLog


class Command(BaseCommand):
    help = "Показывает статистику активных рассылок из логов"

    def handle(self, *args, **options):
        self.stdout.write("Запуск сбора статистики активных рассылок...")

        active_mailings = [
            mailing for mailing in Mailing.objects.all() if mailing.status == "Запущена"
        ]

        results = []

        for mailing in active_mailings:
            successful = MailingLog.objects.filter(
                mailing=mailing, status="sent"
            ).count()
            failed = MailingLog.objects.filter(mailing=mailing, status="failed").count()
            pending = MailingLog.objects.filter(
                mailing=mailing, status="pending"
            ).count()
            total = successful + failed + pending

            results.append(
                {
                    "mailing": mailing,
                    "successful": successful,
                    "failed": failed,
                    "pending": pending,
                    "total": total,
                }
            )

        if results:
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("СТАТИСТИКА АКТИВНЫХ РАССЫЛОК:")
            self.stdout.write("=" * 60)

            for result in results:
                success_rate = (
                    (result["successful"] / result["total"] * 100)
                    if result["total"] > 0
                    else 0
                )

                self.stdout.write(f"\nРассылка: '{result['mailing']}'")
                self.stdout.write(f"  Всего отправок: {result['total']}")
                self.stdout.write(
                    self.style.SUCCESS(f"  Успешно: {result['successful']}")
                )
                self.stdout.write(self.style.ERROR(f"  Ошибок: {result['failed']}"))
                self.stdout.write(
                    self.style.WARNING(f"  В ожидании: {result['pending']}")
                )
                self.stdout.write(f"  Успешность: {success_rate:.1f}%")
                self.stdout.write("-" * 40)

        else:
            self.stdout.write(self.style.WARNING("Активных рассылок не найдено"))

        if results:
            total_successful = sum(result["successful"] for result in results)
            total_failed = sum(result["failed"] for result in results)
            total_pending = sum(result["pending"] for result in results)
            total_all = total_successful + total_failed + total_pending

            overall_success_rate = (
                (total_successful / total_all * 100) if total_all > 0 else 0
            )

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("ОБЩАЯ СТАТИСТИКА:")
            self.stdout.write("=" * 60)
            self.stdout.write(f"Всего активных рассылок: {len(results)}")
            self.stdout.write(f"Всего отправок: {total_all}")
            self.stdout.write(self.style.SUCCESS(f"Всего успешно: {total_successful}"))
            self.stdout.write(self.style.ERROR(f"Всего ошибок: {total_failed}"))
            self.stdout.write(self.style.WARNING(f"Всего в ожидании: {total_pending}"))
            self.stdout.write(f"Общая успешность: {overall_success_rate:.1f}%")
