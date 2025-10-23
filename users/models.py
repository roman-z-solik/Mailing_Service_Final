import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Кастомная модель пользователя"""

    email = models.EmailField(unique=True, verbose_name="Email")
    email_verified = models.BooleanField(
        default=False, verbose_name="Email подтвержден"
    )
    verification_token = models.UUIDField(
        default=uuid.uuid4, editable=False, verbose_name="Токен верификации"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_blocked = models.BooleanField(default=False, verbose_name="Заблокирован")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
        related_name="customuser_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name="user permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        related_name="customuser_set",
        related_query_name="user",
    )

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = "users_customuser"


class Recipients(models.Model):
    """Модель получателей рассылки"""

    email = models.EmailField(verbose_name="Email")
    fullname = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="ФИО"
    )
    comment = models.TextField(blank=True, null=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name="Владелец",
        related_name="recipients",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = "Получатель"
        verbose_name_plural = "Получатели"
        db_table = "users_recipients"
