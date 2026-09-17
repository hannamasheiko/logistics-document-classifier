from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProcessingAttempt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "original_file",
                    models.FileField(upload_to="documents/%Y/%m/%d"),
                ),
                ("original_name", models.CharField(max_length=255)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("page_count", models.PositiveSmallIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PROCESSING", "Processing"),
                            ("ACCEPTED", "Accepted"),
                            ("UNCERTAIN", "Uncertain"),
                            ("FAILED", "Failed"),
                        ],
                        default="PROCESSING",
                        max_length=10,
                    ),
                ),
                (
                    "accepted_label",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("INVOICE", "Invoice"),
                            ("BOL", "Bill of lading"),
                            ("POD", "Proof of delivery"),
                            ("OTHER", "Other"),
                        ],
                        max_length=10,
                        null=True,
                    ),
                ),
                ("routing_score", models.FloatField(blank=True, null=True)),
                (
                    "score_method",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                ("primary_observations", models.JSONField(blank=True, null=True)),
                ("primary_metadata", models.JSONField(blank=True, null=True)),
                (
                    "failure_stage",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "failure_category",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                ("failure_reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-created_at",),
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("accepted_label__isnull", False),
                                ("status", "ACCEPTED"),
                            ),
                            models.Q(
                                models.Q(("status", "ACCEPTED"), _negated=True),
                                ("accepted_label__isnull", True),
                            ),
                            _connector="OR",
                        ),
                        name="accepted_status_has_final_label",
                    )
                ],
            },
        )
    ]
