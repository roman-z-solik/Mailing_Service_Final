from django.contrib import messages
from django.shortcuts import redirect


class OwnerRequiredMixin:
    """Миксин проверки владельца объекта"""

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if (
            obj.owner != request.user
            and not request.user.groups.filter(name="Managers").exists()
        ):
            messages.error(request, "У вас нет прав для выполнения этого действия.")
            return redirect("users:recipient_list")
        return super().dispatch(request, *args, **kwargs)


class ManagerRequiredMixin:
    """Миксин для проверки, что пользователь является менеджером"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.groups.filter(name="Managers").exists():
            messages.error(request, "Доступ разрешен только менеджерам.")
            return redirect("mailing:home")
        return super().dispatch(request, *args, **kwargs)


class UserAccessMixin:
    """Миксин для управления доступом к объектам"""

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        if user.groups.filter(name="Managers").exists():
            return queryset

        if hasattr(queryset.model, "owner"):
            return queryset.filter(owner=user)

        return queryset.none()
