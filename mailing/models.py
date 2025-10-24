from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()


class Mailing(models.Model):
    """Модель рассылки"""

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Владелец", related_name="mailings"
    )
    title = models.CharField(max_length=255, verbose_name="Название рассылки")
    start_time = models.DateTimeField(verbose_name="Время начала")
    end_time = models.DateTimeField(verbose_name="Время окончания")
    message_text = models.TextField(verbose_name="Текст сообщения")
    recipients = models.ManyToManyField("users.Recipients", verbose_name="Получатели")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} (владелец: {self.owner.email})"

    @property
    def status(self):
        """Текущий статус рассылки согласно ТЗ"""
        now = timezone.now()

        if not self.is_active:
            return "Отключена"

        if self.logs.count() == 0:
            return "Создана"

        if now > self.end_time:
            return "Завершена"

        if self.logs.count() > 0 and self.is_active:
            return "Запущена"

        return "Создана"

    @property
    def status_display(self):
        """Отображаемое значение статуса"""
        status_map = {
            "Создана": "Создана",
            "Запущена": "Запущена",
            "Завершена": "Завершена",
            "Отключена": "Отключена",
        }
        return status_map.get(self.status, "Создана")

    @property
    def sent_count(self):
        """Количество отправленных сообщений"""
        return self.logs.filter(status="sent").count()

    @property
    def failed_count(self):
        """Количество неудачных отправлений"""
        return self.logs.filter(status="failed").count()

    @property
    def total_count(self):
        """Общее количество сообщений"""
        return self.logs.count()

    @property
    def success_rate(self):
        """Процент успешных отправлений"""
        if self.total_count == 0:
            return 0
        return round((self.sent_count / self.total_count) * 100, 2)

    def get_cached_stats(self):
        """Получение статистики из кеша с учетом прав доступа"""
        cache_key = f"mailing_{self.id}_stats_user_{self.owner.id}"
        stats = cache.get(cache_key)

        if stats is None:
            stats = {
                "sent_count": self.sent_count,
                "failed_count": self.failed_count,
                "total_count": self.total_count,
                "success_rate": self.success_rate,
            }
            cache.set(cache_key, stats, 60)

        return stats

    @classmethod
    def get_cached_queryset(cls, user):
        """Кешированный queryset"""
        cache_key = f"mailings_user_{user.id}"
        mailings = cache.get(cache_key)

        if mailings is None:
            if user.groups.filter(name="Managers").exists() or user.is_superuser:
                mailings = list(
                    cls.objects.all()
                    .select_related("owner")
                    .prefetch_related("recipients")
                )
            else:
                mailings = list(
                    cls.objects.filter(owner=user)
                    .select_related("owner")
                    .prefetch_related("recipients")
                )

            cache.set(cache_key, mailings, 120)

        return mailings


class MailingLog(models.Model):
    """Модель лога рассылки"""

    STATUS_CHOICES = [
        ("sent", "Успешно"),
        ("failed", "Не успешно"),
        ("pending", "В ожидании"),
    ]

    mailing = models.ForeignKey(
        Mailing, on_delete=models.CASCADE, verbose_name="Рассылка", related_name="logs"
    )
    recipient = models.ForeignKey(
        "users.Recipients", on_delete=models.CASCADE, verbose_name="Получатель"
    )
    attempt_time = models.DateTimeField(auto_now_add=True, verbose_name="Время попытки")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, verbose_name="Статус"
    )
    server_response = models.TextField(
        blank=True, null=True, verbose_name="Ответ сервера"
    )
    error_message = models.TextField(
        blank=True, null=True, verbose_name="Сообщение об ошибке"
    )

    class Meta:
        verbose_name = "Лог рассылки"
        verbose_name_plural = "Логи рассылок"
        ordering = ["-attempt_time"]

    def __str__(self):
        return f"Лог {self.mailing.title} - {self.recipient.email} - {self.status}"

    @property
    def is_successful(self):
        """Была ли отправка успешной"""
        return self.status == "sent"

    @classmethod
    def get_cached_recent_logs(cls, mailing_id, limit=10):
        """Кешированные последние логи"""
        cache_key = f"mailing_{mailing_id}_recent_logs_{limit}"
        logs = cache.get(cache_key)

        if logs is None:
            logs = list(
                cls.objects.filter(mailing_id=mailing_id)
                .select_related("recipient")
                .order_by("-attempt_time")[:limit]
            )
            cache.set(cache_key, logs, 30)

        return logs


class Message(models.Model):
    """Модель шаблона сообщения"""

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Владелец", related_name="messages"
    )
    title = models.CharField(max_length=255, verbose_name="Название шаблона")
    subject = models.CharField(max_length=255, verbose_name="Тема письма")
    body = models.TextField(verbose_name="Текст сообщения")
    is_template = models.BooleanField(default=True, verbose_name="Является шаблоном")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Шаблон сообщения"
        verbose_name_plural = "Шаблоны сообщений"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def use_in_mailing(self, mailing_title):
        """Использование шаблона в рассылке"""
        return {"title": f"{mailing_title} - {self.title}", "message_text": self.body}


class MailingSettings(models.Model):
    """Настройки рассылки (дополнительные параметры)"""

    FREQUENCY_CHOICES = [
        ("once", "Один раз"),
        ("daily", "Ежедневно"),
        ("weekly", "Еженедельно"),
        ("monthly", "Ежемесячно"),
    ]

    mailing = models.OneToOneField(
        Mailing,
        on_delete=models.CASCADE,
        verbose_name="Рассылка",
        related_name="settings",
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="once",
        verbose_name="Периодичность",
    )
    send_time = models.TimeField(blank=True, null=True, verbose_name="Время отправки")
    max_retries = models.PositiveIntegerField(
        default=3, verbose_name="Максимальное количество попыток"
    )
    retry_delay = models.PositiveIntegerField(
        default=60, verbose_name="Задержка между попытками (сек)"
    )
    track_opens = models.BooleanField(
        default=False, verbose_name="Отслеживать открытия"
    )
    track_clicks = models.BooleanField(
        default=False, verbose_name="Отслеживать переходы по ссылкам"
    )

    class Meta:
        verbose_name = "Настройка рассылки"
        verbose_name_plural = "Настройки рассылок"

    def __str__(self):
        return f"Настройки для {self.mailing.title}"


class ClientGroup(models.Model):
    """Группа клиентов для фильтрации"""

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Владелец",
        related_name="client_groups",
    )
    name = models.CharField(max_length=255, verbose_name="Название группы")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    filter_conditions = models.JSONField(
        default=dict,
        verbose_name="Условия фильтрации",
        help_text="JSON с условиями фильтрации клиентов",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Группа клиентов"
        verbose_name_plural = "Группы клиентов"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_recipients_count(self):
        """Количество получателей в группе"""
        from users.models import Recipients

        queryset = Recipients.objects.filter(owner=self.owner)

        if "tag" in self.filter_conditions:
            queryset = queryset.filter(tag__icontains=self.filter_conditions["tag"])
        if "email_domain" in self.filter_conditions:
            queryset = queryset.filter(
                email__endswith=self.filter_conditions["email_domain"]
            )

        return queryset.count()

    @property
    def recipients_count(self):
        return self.get_recipients_count()


@receiver(post_save, sender=Mailing)
def create_mailing_settings(sender, instance, created, **kwargs):
    """Автоматическое создание настроек для новой рассылки"""
    if created and not hasattr(instance, "settings"):
        MailingSettings.objects.create(mailing=instance)


@receiver(post_save, sender=Mailing)
@receiver(post_delete, sender=Mailing)
def invalidate_mailing_cache(sender, instance, **kwargs):
    """Инвалидация кеша при изменении рассылки"""
    user_id = instance.owner.id
    cache.delete_many(
        [
            f"mailings_user_{user_id}",
            f"mailing_{instance.id}_full",
            f"mailing_{instance.id}_stats",
        ]
    )
    for i in range(1, 20):
        cache.delete(f"mailing_{instance.id}_recent_logs_{i}")


@receiver(post_save, sender=MailingLog)
@receiver(post_delete, sender=MailingLog)
def invalidate_logs_cache(sender, instance, **kwargs):
    """Инвалидация кеша логов"""
    cache.delete(f"mailing_{instance.mailing_id}_stats")
    for i in range(1, 20):
        cache.delete(f"mailing_{instance.mailing_id}_recent_logs_{i}")
