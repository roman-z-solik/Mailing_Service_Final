from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html

from .models import ClientGroup, Mailing, MailingLog, MailingSettings, Message

User = get_user_model()


class OwnerFilter(admin.SimpleListFilter):
    """Фильтр по владельцу"""

    title = "Владелец"
    parameter_name = "owner"

    def lookups(self, request, model_admin):
        users = User.objects.all()
        return [(user.id, user.email) for user in users]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(owner_id=self.value())
        return queryset


class StatusFilter(admin.SimpleListFilter):
    """Фильтр по статусу рассылки"""

    title = "Статус"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("scheduled", "Запланирована"),
            ("active", "Активна"),
            ("completed", "Завершена"),
            ("disabled", "Отключена"),
        ]

    def queryset(self, request, queryset):
        from django.utils import timezone

        now = timezone.now()

        if self.value() == "scheduled":
            return queryset.filter(is_active=True, start_time__gt=now)
        elif self.value() == "active":
            return queryset.filter(
                is_active=True, start_time__lte=now, end_time__gte=now
            )
        elif self.value() == "completed":
            return queryset.filter(end_time__lt=now)
        elif self.value() == "disabled":
            return queryset.filter(is_active=False)
        return queryset


class MailingSettingsInline(admin.StackedInline):
    """Inline для настроек рассылки"""

    model = MailingSettings
    extra = 0
    fields = (
        "frequency",
        "send_time",
        "max_retries",
        "retry_delay",
        "track_opens",
        "track_clicks",
    )
    can_delete = False


class MailingLogInline(admin.TabularInline):
    """Inline для логов рассылки"""

    model = MailingLog
    extra = 0
    readonly_fields = (
        "attempt_time",
        "recipient",
        "status",
        "server_response",
        "error_message",
    )
    can_delete = False
    max_num = 10

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    """Админ-панель для рассылок"""

    list_display = (
        "title",
        "owner_email",
        "status_badge",
        "is_active_badge",
        "start_time",
        "end_time",
        "recipients_count",
        "success_rate_display",
        "created_at",
    )
    list_filter = (
        OwnerFilter,
        StatusFilter,
        "is_active",
        "start_time",
        "end_time",
        "created_at",
    )
    search_fields = ("title", "owner__email", "owner__username", "message_text")
    readonly_fields = (
        "created_at",
        "status",
        "sent_count",
        "failed_count",
        "total_count",
        "success_rate",
    )
    fieldsets = (
        (
            "Основная информация",
            {"fields": ("owner", "title", "is_active", "created_at")},
        ),
        ("Содержание", {"fields": ("message_text", "recipients")}),
        ("Время отправки", {"fields": ("start_time", "end_time")}),
        (
            "Статистика",
            {
                "fields": (
                    "status",
                    "sent_count",
                    "failed_count",
                    "total_count",
                    "success_rate",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    inlines = [MailingSettingsInline, MailingLogInline]
    filter_horizontal = ("recipients",)
    date_hierarchy = "created_at"
    list_per_page = 20

    def owner_email(self, obj):
        return obj.owner.email

    owner_email.short_description = "Владелец"
    owner_email.admin_order_field = "owner__email"

    def status_badge(self, obj):
        status_map = {
            "scheduled": ("secondary", "Запланирована"),
            "active": ("success", "Активна"),
            "completed": ("info", "Завершена"),
            "disabled": ("danger", "Отключена"),
        }
        color, text = status_map.get(obj.status, ("secondary", "Неизвестно"))
        return format_html('<span class="badge bg-{}">{}</span>', color, text)

    status_badge.short_description = "Статус"

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="badge bg-success">✓ Активна</span>')
        return format_html('<span class="badge bg-danger">✗ Неактивна</span>')

    is_active_badge.short_description = "Активность"

    def recipients_count(self, obj):
        return obj.recipients.count()

    recipients_count.short_description = "Получателей"

    def success_rate_display(self, obj):
        return f"{obj.success_rate}%"

    success_rate_display.short_description = "Успешных отправок"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related("owner").prefetch_related("recipients", "logs")
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Ограничение выбора владельца"""
        if db_field.name == "owner":
            kwargs["queryset"] = User.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Ограничение выбора получателей"""
        if db_field.name == "recipients":
            from users.models import Recipients

            kwargs["queryset"] = Recipients.objects.all()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        """Права на изменение: суперпользователь или владелец"""
        if obj is None:
            return True
        return request.user.is_superuser or obj.owner == request.user

    def has_delete_permission(self, request, obj=None):
        """Права на удаление: суперпользователь или владелец"""
        if obj is None:
            return True
        return request.user.is_superuser or obj.owner == request.user


@admin.register(MailingLog)
class MailingLogAdmin(admin.ModelAdmin):
    """Админ-панель для логов рассылок"""

    list_display = (
        "id",
        "mailing_title",
        "recipient_email",
        "attempt_time",
        "status_badge",
        "server_response_preview",
        "error_message_preview",
    )
    list_filter = ("status", "attempt_time", "mailing__owner")
    search_fields = (
        "mailing__title",
        "recipient__email",
        "server_response",
        "error_message",
    )
    readonly_fields = (
        "mailing",
        "recipient",
        "attempt_time",
        "status",
        "server_response",
        "error_message",
    )
    date_hierarchy = "attempt_time"
    list_per_page = 50

    def mailing_title(self, obj):
        return obj.mailing.title

    mailing_title.short_description = "Рассылка"
    mailing_title.admin_order_field = "mailing__title"

    def recipient_email(self, obj):
        return obj.recipient.email

    recipient_email.short_description = "Получатель"
    recipient_email.admin_order_field = "recipient__email"

    def status_badge(self, obj):
        status_map = {
            "sent": ("success", "Отправлено"),
            "failed": ("danger", "Ошибка"),
            "pending": ("warning", "В ожидании"),
        }
        color, text = status_map.get(obj.status, ("secondary", "Неизвестно"))
        return format_html('<span class="badge bg-{}">{}</span>', color, text)

    status_badge.short_description = "Статус"

    def server_response_preview(self, obj):
        if obj.server_response:
            return (
                obj.server_response[:50] + "..."
                if len(obj.server_response) > 50
                else obj.server_response
            )
        return "-"

    server_response_preview.short_description = "Ответ сервера"

    def error_message_preview(self, obj):
        if obj.error_message:
            return (
                obj.error_message[:50] + "..."
                if len(obj.error_message) > 50
                else obj.error_message
            )
        return "-"

    error_message_preview.short_description = "Ошибка"

    def has_add_permission(self, request):
        """Запрещаем создание логов вручную"""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещаем изменение логов"""
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related("mailing", "recipient")
        return qs


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Админ-панель для шаблонов сообщений"""

    list_display = (
        "title",
        "owner_email",
        "subject",
        "is_template_badge",
        "body_preview",
        "created_at",
    )
    list_filter = ("is_template", "created_at", "owner")
    search_fields = ("title", "subject", "body", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Основная информация",
            {"fields": ("owner", "title", "subject", "is_template")},
        ),
        ("Содержание", {"fields": ("body",)}),
        ("Даты", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    list_per_page = 20

    def owner_email(self, obj):
        return obj.owner.email

    owner_email.short_description = "Владелец"
    owner_email.admin_order_field = "owner__email"

    def is_template_badge(self, obj):
        if obj.is_template:
            return format_html('<span class="badge bg-info">Шаблон</span>')
        return format_html('<span class="badge bg-secondary">Сообщение</span>')

    is_template_badge.short_description = "Тип"

    def body_preview(self, obj):
        return obj.body[:100] + "..." if len(obj.body) > 100 else obj.body

    body_preview.short_description = "Предпросмотр"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related("owner")
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            kwargs["queryset"] = User.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        return request.user.is_superuser or obj.owner == request.user

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return True
        return request.user.is_superuser or obj.owner == request.user


@admin.register(MailingSettings)
class MailingSettingsAdmin(admin.ModelAdmin):
    """Админ-панель для настроек рассылок"""

    list_display = (
        "mailing_title",
        "frequency_display",
        "send_time",
        "max_retries",
        "retry_delay",
        "track_opens",
        "track_clicks",
    )
    list_filter = ("frequency", "track_opens", "track_clicks")
    search_fields = ("mailing__title",)
    readonly_fields = ("mailing",)

    def mailing_title(self, obj):
        return obj.mailing.title

    mailing_title.short_description = "Рассылка"
    mailing_title.admin_order_field = "mailing__title"

    def frequency_display(self, obj):
        frequency_map = {
            "once": "Один раз",
            "daily": "Ежедневно",
            "weekly": "Еженедельно",
            "monthly": "Ежемесячно",
        }
        return frequency_map.get(obj.frequency, obj.frequency)

    frequency_display.short_description = "Периодичность"

    def has_add_permission(self, request):
        """Настройки создаются автоматически через сигнал"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещаем удаление настроек"""
        return False


@admin.register(ClientGroup)
class ClientGroupAdmin(admin.ModelAdmin):
    """Админ-панель для групп клиентов"""

    list_display = ("name", "owner_email", "recipients_count", "created_at")
    list_filter = ("created_at", "owner")
    search_fields = ("name", "description", "owner__email")
    readonly_fields = ("created_at", "recipients_count")
    fieldsets = (
        ("Основная информация", {"fields": ("owner", "name", "description")}),
        (
            "Условия фильтрации",
            {"fields": ("filter_conditions",), "classes": ("collapse",)},
        ),
        (
            "Статистика",
            {"fields": ("recipients_count", "created_at"), "classes": ("collapse",)},
        ),
    )

    def owner_email(self, obj):
        return obj.owner.email

    owner_email.short_description = "Владелец"
    owner_email.admin_order_field = "owner__email"

    def recipients_count(self, obj):
        return obj.recipients_count

    recipients_count.short_description = "Количество получателей"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related("owner")
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "owner":
            kwargs["queryset"] = User.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        return request.user.is_superuser or obj.owner == request.user

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return True
        return request.user.is_superuser or obj.owner == request.user
