from django.urls import path

from documents import views

app_name = "documents"

urlpatterns = [
    path("", views.upload_view, name="upload"),
    path("history/", views.history_view, name="history"),
    path("attempts/<int:pk>/", views.result_view, name="result"),
    path("attempts/<int:pk>/original/", views.original_view, name="original"),
]
