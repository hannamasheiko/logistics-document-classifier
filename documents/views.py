from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from documents.forms import DocumentUploadForm
from documents.models import ProcessingAttempt
from documents.services.processing import run_classification


def upload_view(request):
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            attempt = form.save()
            run_classification(attempt)
            return redirect("documents:result", pk=attempt.pk)
    else:
        form = DocumentUploadForm()
    return render(request, "documents/upload.html", {"form": form})


def result_view(request, pk):
    attempt = get_object_or_404(ProcessingAttempt, pk=pk)
    return render(request, "documents/result.html", {"attempt": attempt})


def history_view(request):
    attempts = ProcessingAttempt.objects.all()
    return render(request, "documents/history.html", {"attempts": attempts})


def original_view(request, pk):
    attempt = get_object_or_404(ProcessingAttempt, pk=pk)
    return FileResponse(
        attempt.original_file.open("rb"),
        content_type="application/pdf",
        filename=attempt.original_name,
        as_attachment=False,
    )
