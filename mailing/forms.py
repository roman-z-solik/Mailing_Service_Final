
from django import forms

from users.models import Recipients

from .models import Mailing, Message


class MailingForm(forms.ModelForm):
    class Meta:
        model = Mailing
        fields = [
            "title",
            "start_time",
            "end_time",
            "message_text",
            "recipients",
            "is_active",
        ]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "message_text": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.user and not (
            self.user.groups.filter(name="Managers").exists() or self.user.is_superuser
        ):
            self.fields["recipients"].queryset = Recipients.objects.filter(
                owner=self.user
            )
        else:
            self.fields["recipients"].queryset = Recipients.objects.all()

        if self.user and self.user.groups.filter(name="Managers").exists():
            self.fields["is_active"].widget = forms.HiddenInput()

        if self.user:
            user_messages = Message.objects.filter(owner=self.user, is_template=True)
            self.fields["existing_message"] = forms.ModelChoiceField(
                queryset=user_messages,
                required=False,
                label="Выбрать шаблон сообщения",
                empty_label="-- Выберите шаблон --",
            )

        if self.instance.pk and hasattr(self.instance, "message_text"):
            self.fields["message_text"].initial = self.instance.message_text
        elif self.initial.get("existing_message"):
            try:
                message = Message.objects.get(
                    id=self.initial["existing_message"], owner=self.user
                )
                self.fields["message_text"].initial = message.body
            except Message.DoesNotExist:
                pass

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        existing_message = cleaned_data.get("existing_message")

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                "Время окончания должно быть позже времени начала."
            )

        if existing_message:
            cleaned_data["message_text"] = existing_message.body

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if not instance.pk and self.user:
            instance.owner = self.user

        if commit:
            instance.save()
            self.save_m2m()

        return instance
