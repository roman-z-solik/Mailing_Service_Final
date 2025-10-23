from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect


class OwnerRequiredMixin(UserPassesTestMixin):
    """Миксин для проверки, что пользователь является владельцем объекта"""

    def test_func(self):
        obj = self.get_object()
        return obj.owner == self.request.user

    def handle_no_permission(self):
        from django.contrib import messages
        from django.shortcuts import redirect

        messages.error(self.request, "У вас нет прав для выполнения этого действия.")
        return redirect("mailing:mailing_list")


class ManagerRequiredMixin(UserPassesTestMixin):
    """Миксин для проверки, что пользователь является менеджером"""

    def test_func(self):
        return (
            self.request.user.groups.filter(name="Managers").exists()
            or self.request.user.is_superuser
        )

    def handle_no_permission(self):
        messages.error(self.request, "Доступ разрешен только менеджерам.")
        return redirect("mailing:mailing_list")


class UserAccessMixin:
    """Миксин для управления доступом к объектам"""

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.groups.filter(name="Managers").exists() or user.is_superuser:
            return queryset
        else:
            if hasattr(queryset.model, "mailing"):
                return queryset.filter(mailing__owner=user)
            elif hasattr(queryset.model, "owner"):
                return queryset.filter(owner=user)
            return queryset.none()