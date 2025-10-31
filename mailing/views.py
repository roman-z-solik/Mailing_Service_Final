from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from .forms import MailingForm
from .models import Mailing, MailingLog, Message
from .permissions import ManagerRequiredMixin, OwnerRequiredMixin, UserAccessMixin


class HomeView(TemplateView):
    """Главная страница"""

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_authenticated:
            from django.contrib.auth import get_user_model

            from users.models import Recipients

            User = get_user_model()

            cache_key = f"home_stats_{user.id}"
            cached_data = cache.get(cache_key)

            if cached_data is None:
                if user.groups.filter(name="Managers").exists() or user.is_superuser:
                    data = {
                        "total_mailings": Mailing.objects.count(),
                        "active_mailings": Mailing.objects.filter(
                            is_active=True
                        ).count(),
                        "total_users": User.objects.count(),
                        "total_recipients": Recipients.objects.count(),
                    }
                else:
                    data = {
                        "total_mailings": Mailing.objects.filter(owner=user).count(),
                        "active_mailings": Mailing.objects.filter(
                            owner=user, is_active=True
                        ).count(),
                        "total_recipients": Recipients.objects.filter(
                            owner=user
                        ).count(),
                    }
                cache.set(cache_key, data, 300)  # 5 минут
                cached_data = data

            context.update(cached_data)

        return context


class MailingListView(LoginRequiredMixin, UserAccessMixin, ListView):
    """Список рассылок"""

    model = Mailing
    template_name = "mailing/mailing_list.html"
    context_object_name = "mailings"
    paginate_by = 10

    def get_queryset(self):
        if (
            self.request.user.groups.filter(name="Managers").exists()
            or self.request.user.is_superuser
        ):
            queryset = Mailing.objects.all().select_related("owner")
        else:
            queryset = Mailing.objects.filter(owner=self.request.user).select_related(
                "owner"
            )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_manager"] = (
            self.request.user.groups.filter(name="Managers").exists()
            or self.request.user.is_superuser
        )
        context["total_mailings"] = context["mailings"].count()
        return context


class MailingDetailView(LoginRequiredMixin, UserAccessMixin, DetailView):
    """Детальный просмотр рассылки"""

    model = Mailing
    template_name = "mailing/mailing_detail.html"
    context_object_name = "mailing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mailing = self.object
        user = self.request.user

        context["can_edit"] = (
            mailing.owner == user or user.groups.filter(name="Managers").exists()
        )

        if (
            mailing.owner == user
            or user.groups.filter(name="Managers").exists()
            or user.is_superuser
        ):
            context["recent_logs"] = MailingLog.get_cached_recent_logs(mailing.id, 10)
        else:
            context["recent_logs"] = []

        if (
            mailing.owner == user
            or user.groups.filter(name="Managers").exists()
            or user.is_superuser
        ):
            stats = mailing.get_cached_stats()
            total_messages = stats["total_count"]
            sent_messages = stats["sent_count"]
            failed_messages = stats["failed_count"]
        else:
            total_messages = 0
            sent_messages = 0
            failed_messages = 0

        context.update(
            {
                "total_messages": total_messages,
                "sent_messages": sent_messages,
                "failed_messages": failed_messages,
                "pending_messages": total_messages - sent_messages - failed_messages,
            }
        )

        return context


class MailingCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Создание новой рассылки"""

    model = Mailing
    form_class = MailingForm
    template_name = "mailing/mailing_form.html"
    success_url = reverse_lazy("mailing:mailing_list")
    success_message = "Рассылка успешно создана"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.is_active = True

        user_id = self.request.user.id
        cache_keys_to_delete = [
            f"mailings_user_{user_id}",
            f"home_stats_{user_id}",
            f"mailing_list_{user_id}",
        ]

        for key in cache_keys_to_delete:
            cache.delete(key)

        if self.request.user.groups.filter(name="Managers").exists():
            cache.delete_pattern("*mailings_user_*")
            cache.delete_pattern("*home_stats_*")

        return super().form_valid(form)


class MailingUpdateView(
    LoginRequiredMixin, OwnerRequiredMixin, SuccessMessageMixin, UpdateView
):
    """Редактирование рассылки"""

    model = Mailing
    form_class = MailingForm
    template_name = "mailing/mailing_form.html"
    success_url = reverse_lazy("mailing:mailing_list")
    success_message = "Рассылка успешно обновлена"

    def form_valid(self, form):
        if not (
            self.request.user.groups.filter(name="Managers").exists()
            or self.request.user.is_superuser
        ):
            form.instance.is_active = self.get_object().is_active

        cache.delete(f"mailings_user_{self.request.user.id}")
        cache.delete(f"home_stats_{self.request.user.id}")

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class MailingDeleteView(
    LoginRequiredMixin, OwnerRequiredMixin, SuccessMessageMixin, DeleteView
):
    """Удаление рассылки"""

    model = Mailing
    template_name = "mailing/mailing_confirm_delete.html"
    success_url = reverse_lazy("mailing:mailing_list")
    success_message = "Рассылка успешно удалена"

    def delete(self, request, *args, **kwargs):
        cache.delete(f"mailings_user_{self.request.user.id}")
        cache.delete(f"home_stats_{self.request.user.id}")

        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


class MailingToggleActiveView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Включение/выключение рассылки (только для менеджеров)"""

    def post(self, request, pk):
        mailing = get_object_or_404(Mailing, pk=pk)

        if (
            not request.user.groups.filter(name="Managers").exists()
            and not request.user.is_superuser
        ):
            messages.error(request, "У вас нет прав для управления рассылками.")
            return redirect("mailing:mailing_list")

        mailing.is_active = not mailing.is_active
        mailing.save()

        cache.delete(f"mailings_user_{mailing.owner.id}")
        cache.delete(f"home_stats_{mailing.owner.id}")

        action = "остановлена" if not mailing.is_active else "активирована"
        messages.success(request, f'Рассылка "{mailing.title}" {action} менеджером.')

        return redirect("mailing:mailing_list")


class MailingSendView(LoginRequiredMixin, UserAccessMixin, View):
    """Отправка рассылки"""

    def post(self, request, pk):
        mailing = get_object_or_404(Mailing, pk=pk)

        if not (
            mailing.owner == request.user
            or request.user.groups.filter(name="Managers").exists()
        ):
            messages.error(request, "У вас нет прав для отправки этой рассылки.")
            return redirect("mailing:mailing_list")

        if mailing.recipients.count() == 0:
            messages.error(request, "Невозможно отправить рассылку: нет получателей.")
            return redirect("mailing:mailing_detail", pk=pk)

        if not mailing.is_active:
            messages.error(
                request, "Невозможно отправить рассылку: рассылка отключена менеджером."
            )
            return redirect("mailing:mailing_detail", pk=pk)

        if timezone.now() > mailing.end_time:
            messages.error(
                request, "Невозможно отправить рассылку: время рассылки истекло."
            )
            return redirect("mailing:mailing_detail", pk=pk)

        try:
            sent_count = 0
            failed_count = 0

            for recipient in mailing.recipients.all():
                try:
                    send_mail(
                        subject=mailing.title,
                        message=mailing.message_text,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient.email],
                        fail_silently=False,
                    )

                    MailingLog.objects.create(
                        mailing=mailing,
                        recipient=recipient,
                        status="sent",
                        server_response="250 OK: Message accepted",
                        error_message="",
                    )
                    sent_count += 1

                except Exception as e:
                    MailingLog.objects.create(
                        mailing=mailing,
                        recipient=recipient,
                        status="failed",
                        server_response="",
                        error_message=str(e),
                    )
                    failed_count += 1

            cache.delete(f"mailing_{mailing.id}_stats")
            mailing.get_cached_stats()

            messages.success(
                request,
                f"Рассылка отправлена! Успешно: {sent_count}, Ошибок: {failed_count}",
            )

        except Exception as e:
            messages.error(request, f"Ошибка при отправке рассылки: {str(e)}")

        return redirect("mailing:mailing_detail", pk=pk)


class MailingStatsView(LoginRequiredMixin, ListView):
    """Статистика"""

    model = Mailing
    template_name = "mailing/mailing_stats.html"
    context_object_name = "stats_data"

    def get_queryset(self):
        user = self.request.user

        if user.groups.filter(name="Managers").exists() or user.is_superuser:
            mailings = Mailing.objects.all()
        else:
            mailings = Mailing.objects.filter(owner=user)

        stats_data = []
        for mailing in mailings:
            stats = mailing.get_cached_stats()
            stats_data.append(
                {
                    "mailing": mailing,
                    "total_messages": stats["total_count"],
                    "sent_messages": stats["sent_count"],
                    "failed_messages": stats["failed_count"],
                    "success_rate": stats["success_rate"],
                }
            )

        return stats_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_manager"] = self.request.user.groups.filter(
            name="Managers"
        ).exists()

        stats_data = context["stats_data"]
        total_messages = sum(stat["total_messages"] for stat in stats_data)
        successful_messages = sum(stat["sent_messages"] for stat in stats_data)
        failed_messages = sum(stat["failed_messages"] for stat in stats_data)

        context.update(
            {
                "total_messages": total_messages,
                "successful_messages": successful_messages,
                "failed_messages": failed_messages,
                "overall_success_rate": round(
                    (
                        (successful_messages / total_messages * 100)
                        if total_messages > 0
                        else 0
                    ),
                    1,
                ),
            }
        )

        return context


class MailingLogListView(LoginRequiredMixin, UserAccessMixin, ListView):
    """Список логов рассылок"""

    model = MailingLog
    template_name = "mailing/mailinglog_list.html"
    context_object_name = "logs"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        if user.groups.filter(name="Managers").exists() or user.is_superuser:
            queryset = MailingLog.objects.all()
        else:
            queryset = MailingLog.objects.filter(mailing__owner=user)

        queryset = queryset.select_related("mailing", "recipient")

        mailing_id = self.request.GET.get("mailing_id")
        if mailing_id:
            if user.groups.filter(name="Managers").exists() or user.is_superuser:
                queryset = queryset.filter(mailing_id=mailing_id)
            else:
                queryset = queryset.filter(mailing_id=mailing_id, mailing__owner=user)

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-attempt_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context["mailing_id"] = self.request.GET.get("mailing_id", "")
        context["status"] = self.request.GET.get("status", "")

        if user.groups.filter(name="Managers").exists() or user.is_superuser:
            context["mailings"] = Mailing.objects.all()
        else:
            context["mailings"] = Mailing.objects.filter(owner=user)

        return context


class MessageCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Создание нового шаблона сообщения"""

    model = Message
    fields = ["title", "subject", "body", "is_template"]
    template_name = "mailing/message_form.html"
    success_url = reverse_lazy("mailing:message_list")
    success_message = "Шаблон сообщения успешно создан"

    def form_valid(self, form):
        form.instance.owner = self.request.user

        cache.delete(f"messages_user_{self.request.user.id}")
        cache.delete(f"home_stats_{self.request.user.id}")

        return super().form_valid(form)


class MessageListView(LoginRequiredMixin, UserAccessMixin, ListView):
    """Список шаблонов сообщений"""

    model = Message
    template_name = "mailing/message_list.html"
    context_object_name = "messages"
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if not (user.groups.filter(name="Managers").exists() or user.is_superuser):
            queryset = queryset.filter(owner=user)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context["is_manager"] = (
            user.groups.filter(name="Managers").exists() or user.is_superuser
        )

        full_queryset = self.get_queryset()

        context["templates_count"] = full_queryset.filter(is_template=True).count()

        active_count = 0
        for message in full_queryset:
            if hasattr(message, "mailing_set") and message.mailing_set.exists():
                active_count += 1
        context["active_in_mailings"] = active_count

        return context


class MessageDetailView(LoginRequiredMixin, UserAccessMixin, DetailView):
    """Детальный просмотр шаблона сообщения"""

    model = Message
    template_name = "mailing/message_detail.html"
    context_object_name = "message"


class MessageUpdateView(
    LoginRequiredMixin, OwnerRequiredMixin, SuccessMessageMixin, UpdateView
):
    """Редактирование шаблона сообщения"""

    model = Message
    fields = ["title", "subject", "body", "is_template"]
    template_name = "mailing/message_form.html"
    success_url = reverse_lazy("mailing:message_list")
    success_message = "Шаблон сообщения успешно обновлен"

    def form_valid(self, form):
        cache.delete(f"messages_user_{self.request.user.id}")
        cache.delete(f"home_stats_{self.request.user.id}")

        return super().form_valid(form)


class MessageDeleteView(
    LoginRequiredMixin, OwnerRequiredMixin, SuccessMessageMixin, DeleteView
):
    """Удаление шаблона сообщения"""

    model = Message
    template_name = "mailing/message_confirm_delete.html"
    success_url = reverse_lazy("mailing:message_list")
    success_message = "Шаблон сообщения успешно удален"

    def delete(self, request, *args, **kwargs):
        cache.delete(f"messages_user_{self.request.user.id}")
        cache.delete(f"home_stats_{self.request.user.id}")

        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)
