from django.contrib import admin

from users.models import Recipients


@admin.register(Recipients)
class RecipientsAdmin(admin.ModelAdmin):
    """Декоратор и класс RecipientsAdmin настраивают отображение и поведение модели Recipients в
    административной панели Django."""

    verbose_name = "Новый пользователь"
    list_display = ("email", "fullname", "comment")
    search_fields = (
        "email",
        "is_staff",
        "is_active",
    )
