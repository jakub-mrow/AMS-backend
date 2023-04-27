from django.db import models
from django.contrib.auth.models import User


class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="task owner")
    description = models.CharField(max_length=128, help_text="Task description")
