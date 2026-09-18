from django.db import models
from django.db.models import Q


class ProcessingAttempt(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "PROCESSING", "Processing"
        ACCEPTED = "ACCEPTED", "Accepted"
        UNCERTAIN = "UNCERTAIN", "Uncertain"
        FAILED = "FAILED", "Failed"

    class Label(models.TextChoices):
        INVOICE = "INVOICE", "Invoice"
        BOL = "BOL", "Bill of lading"
        POD = "POD", "Proof of delivery"
        OTHER = "OTHER", "Other"

    original_file = models.FileField(upload_to="documents/%Y/%m/%d")
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    page_count = models.PositiveSmallIntegerField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PROCESSING,
    )
    accepted_label = models.CharField(
        max_length=10,
        choices=Label.choices,
        null=True,
        blank=True,
    )
    routing_score = models.FloatField(null=True, blank=True)
    score_method = models.CharField(max_length=100, null=True, blank=True)

    primary_observations = models.JSONField(null=True, blank=True)
    primary_metadata = models.JSONField(null=True, blank=True)

    fallback_observations = models.JSONField(null=True, blank=True)
    fallback_metadata = models.JSONField(null=True, blank=True)

    failure_stage = models.CharField(max_length=100, null=True, blank=True)
    failure_category = models.CharField(max_length=100, null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)

    class ExtractionStatus(models.TextChoices):
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"
        COMPLETED = "COMPLETED", "Completed"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    extraction_status = models.CharField(
        max_length=20,
        choices=ExtractionStatus.choices,
        default=ExtractionStatus.NOT_APPLICABLE,
    )
    extraction_result = models.JSONField(null=True, blank=True)
    extraction_metadata = models.JSONField(null=True, blank=True)
    extraction_failure_category = models.CharField(max_length=100, null=True, blank=True)
    extraction_failure_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="ACCEPTED", accepted_label__isnull=False)
                    | (~Q(status="ACCEPTED") & Q(accepted_label__isnull=True))
                ),
                name="accepted_status_has_final_label",
            )
        ]

    def __str__(self) -> str:
        return f"Attempt {self.pk}: {self.original_name}"
