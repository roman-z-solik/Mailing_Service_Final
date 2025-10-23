from rest_framework import serializers

from .models import CustomUser, Recipients


class RecipientsSerializer(serializers.ModelSerializer):
    """Сериализатор модели получателей"""

    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Recipients
        fields = [
            "id",
            "email",
            "fullname",
            "comment",
            "created_at",
            "owner",
            "owner_email",
        ]
        read_only_fields = ["owner", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор модели пользователя"""

    recipients_count = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "is_blocked",
            "email_verified",
            "created_at",
            "recipients_count",
        ]
        read_only_fields = ["id", "email_verified", "created_at", "recipients_count"]

    def get_recipients_count(self, obj):
        return obj.recipients.count()
