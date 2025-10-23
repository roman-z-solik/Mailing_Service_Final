from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import (
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    CustomUserCreationForm,
    EmailAuthenticationForm,
    RecipientForm,
    UserProfileForm,
)
from .mixins import ManagerRequiredMixin, OwnerRequiredMixin, UserAccessMixin
from .models import Recipients

User = get_user_model()


class RegisterView(SuccessMessageMixin, CreateView):
    """Представление регистрации и верификации пользователя"""

    form_class = CustomUserCreationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:login")
    success_message = (
        "Регистрация успешна! Проверьте вашу почту для подтверждения email."
    )

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        self.send_verification_email(user)

        return response


    def send_verification_email(self, user):
        """Отправка email для подтверждения регистрации"""
        current_site = get_current_site(self.request)
        mail_subject = "Подтверждение регистрации - Система рассылок"

        html_message = render_to_string(
            "users/email_verification.html",
            {
                "user": user,
                "domain": current_site.domain,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": user.verification_token,
            },
        )

        text_message = f"""
        Подтверждение регистрации в системе рассылок

        Здравствуйте, {user.username}!

        Благодарим вас за регистрацию в системе управления рассылками.

        Для завершения регистрации и активации вашего аккаунта, перейдите по ссылке:
        http://{current_site.domain}/users/verify/{urlsafe_base64_encode(force_bytes(user.pk))}/{user.verification_token}/

        Если вы не регистрировались в нашей системе, проигнорируйте это письмо.

        ---
        Это автоматическое сообщение, пожалуйста, не отвечайте на него.
        Система управления рассылками
        """

        send_mail(
            mail_subject, text_message, None, [user.email], html_message=html_message
        )


def verify_email(request, uidb64, token):
    """Подтверждение email пользователя"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and str(user.verification_token) == token:
        user.email_verified = True
        user.is_active = True
        user.save()

        login(request, user)

        messages.success(
            request, "Ваш email успешно подтвержден! Добро пожаловать в систему."
        )
        return redirect("mailing:home")
    else:
        messages.error(
            request, "Ссылка для подтверждения недействительна или устарела."
        )
        return redirect("users:register")


class CustomLoginView(SuccessMessageMixin, LoginView):
    """Представление входа в систему"""

    form_class = EmailAuthenticationForm
    template_name = "users/login.html"
    success_message = "Добро пожаловать!"

    def form_valid(self, form):
        user = form.get_user()
        if not user.email_verified:
            messages.error(
                self.request, "Пожалуйста, подтвердите ваш email перед входом."
            )
            return self.form_invalid(form)

        if hasattr(user, "is_blocked") and user.is_blocked:
            messages.error(
                self.request, "Ваш аккаунт заблокирован. Обратитесь к администратору."
            )
            return self.form_invalid(form)

        return super().form_valid(form)


def custom_logout(request):
    """Функция выхода из системы"""
    logout(request)
    messages.info(request, "Вы успешно вышли из системы.")
    return redirect("mailing:home")


class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    """Представление сброса пароля"""

    form_class = CustomPasswordResetForm
    template_name = "users/password_reset.html"
    email_template_name = "users/password_reset_email.html"
    success_url = reverse_lazy("users:password_reset_done")
    success_message = "Инструкции по сбросу пароля отправлены на ваш email."


class CustomPasswordResetDoneView(PasswordResetDoneView):
    """Страница подтверждения отправки сброса пароля"""

    template_name = "users/password_reset_done.html"


class CustomPasswordResetConfirmView(SuccessMessageMixin, PasswordResetConfirmView):
    """Представление подтверждения сброса пароля"""

    form_class = CustomSetPasswordForm
    template_name = "users/password_reset_confirm.html"
    success_url = reverse_lazy("users:password_reset_complete")
    success_message = "Пароль успешно изменен!"


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """Страница завершения сброса пароля"""

    template_name = "users/password_reset_complete.html"


class RecipientListView(LoginRequiredMixin, UserAccessMixin, ListView):
    """Представление списка получателей"""

    model = Recipients
    template_name = "users/recipient_list.html"
    context_object_name = "recipients"
    paginate_by = 10
    ordering = ["-created_at"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_manager"] = self.request.user.groups.filter(
            name="Managers"
        ).exists()
        return context


class RecipientDetailView(LoginRequiredMixin, UserAccessMixin, DetailView):
    """Детальный просмотр получателя"""

    model = Recipients
    template_name = "users/recipient_detail.html"
    context_object_name = "recipient"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_edit"] = (
            self.object.owner == self.request.user
            or self.request.user.groups.filter(name="Managers").exists()
        )
        return context


class RecipientCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Создание нового получателя"""

    model = Recipients
    form_class = RecipientForm
    template_name = "users/recipient_form.html"
    success_url = reverse_lazy("users:recipient_list")
    success_message = "Получатель успешно создан"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class RecipientUpdateView(
    LoginRequiredMixin, OwnerRequiredMixin, SuccessMessageMixin, UpdateView
):
    """Редактирование получателя"""

    model = Recipients
    form_class = RecipientForm
    template_name = "users/recipient_form.html"
    success_url = reverse_lazy("users:recipient_list")
    success_message = "Получатель успешно обновлен"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class RecipientDeleteView(
    LoginRequiredMixin, OwnerRequiredMixin, SuccessMessageMixin, DeleteView
):
    """Удаление получателя"""

    model = Recipients
    template_name = "users/recipient_confirm_delete.html"
    success_url = reverse_lazy("users:recipient_list")
    success_message = "Получатель успешно удален"

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


class UserListView(LoginRequiredMixin, ManagerRequiredMixin, ListView):
    """Список пользователей (только для менеджеров)"""

    model = User
    template_name = "users/user_list.html"
    context_object_name = "users"
    paginate_by = 10

    def get_queryset(self):
        return User.objects.all().order_by("-date_joined")


class UserBlockToggleView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Блокировка/разблокировка пользователя"""

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_blocked = not user.is_blocked
        user.save()

        action = "заблокирован" if user.is_blocked else "разблокирован"
        messages.success(request, f"Пользователь {user.email} {action}.")

        return redirect("users:user_list")


class UserDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о пользователе1"""

    model = User
    template_name = "users/user_detail.html"
    context_object_name = "user_object"

    def get_object(self, queryset=None):
        return User.objects.get(pk=self.request.user.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = User.objects.get(pk=self.request.user.pk)
        context["user_object"] = user
        context["recipients_count"] = user.recipients.count()
        return context


class UserProfileUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Редактирование профиля пользователя"""
    model = User
    form_class = UserProfileForm
    template_name = "users/user_profile_edit.html"
    success_message = "Профиль успешно обновлен"

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, self.object)
        return response

    def get_success_url(self):
        return reverse_lazy('users:user_detail', kwargs={'pk': self.request.user.pk})