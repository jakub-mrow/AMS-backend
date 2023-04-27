from rest_framework import serializers

from ams import models


class TaskSerializer(serializers.ModelSerializer):
    description = serializers.CharField(help_text="description")

    class Meta:
        model = models.Task
        fields = ("description", )
