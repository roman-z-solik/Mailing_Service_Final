from django.urls import path

from . import views

app_name = "mailing"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("mailings/", views.MailingListView.as_view(), name="mailing_list"),
    path("mailings/create/", views.MailingCreateView.as_view(), name="mailing_create"),
    path(
        "mailings/<int:pk>/", views.MailingDetailView.as_view(), name="mailing_detail"
    ),
    path(
        "mailings/<int:pk>/update/",
        views.MailingUpdateView.as_view(),
        name="mailing_update",
    ),
    path(
        "mailings/<int:pk>/delete/",
        views.MailingDeleteView.as_view(),
        name="mailing_delete",
    ),
    path(
        "mailings/<int:pk>/toggle-active/",
        views.MailingToggleActiveView.as_view(),
        name="mailing_toggle_active",
    ),
    path(
        "mailings/<int:pk>/send/", views.MailingSendView.as_view(), name="mailing_send"
    ),
    path("stats/", views.MailingStatsView.as_view(), name="mailing_stats"),
    path("logs/", views.MailingLogListView.as_view(), name="mailing_logs"),
    path("messages/create/", views.MessageCreateView.as_view(), name="message_create"),
    path("messages/", views.MessageListView.as_view(), name="message_list"),
    path(
        "messages/<int:pk>/", views.MessageDetailView.as_view(), name="message_detail"
    ),
    path(
        "messages/<int:pk>/update/",
        views.MessageUpdateView.as_view(),
        name="message_update",
    ),
    path(
        "messages/<int:pk>/delete/",
        views.MessageDeleteView.as_view(),
        name="message_delete",
    ),
]
