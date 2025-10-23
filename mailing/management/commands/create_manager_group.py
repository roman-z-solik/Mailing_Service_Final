
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from mailing.models import Client, Mailing, MailingAttempt, Message
from users.models import CustomUser


class Command(BaseCommand):
    help = "Создает группу Менеджеры с нужными разрешениями"

    def handle(self, *args, **options):
        manager_group, created = Group.objects.get_or_create(name="Менеджеры")

        if created:
            self.stdout.write(self.style.SUCCESS('Группа "Менеджеры" создана'))
        else:
            self.stdout.write('Группа "Менеджеры" уже существует')
            return

        # Добавляем разрешения на просмотр
        content_types = [
            ContentType.objects.get_for_model(Mailing),
            ContentType.objects.get_for_model(Client),
            ContentType.objects.get_for_model(Message),
            ContentType.objects.get_for_model(MailingAttempt),
            ContentType.objects.get_for_model(CustomUser),
        ]

        view_permissions = Permission.objects.filter(
            content_type__in=content_types, codename__startswith="view_"
        )

        for perm in view_permissions:
            manager_group.permissions.add(perm)

        self.stdout.write(self.style.SUCCESS('Разрешения добавлены группе "Менеджеры"'))
