import logging

from ams import models, serializers

from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import IsObjectOwner

logger = logging.getLogger(__name__)


class TaskViewSet(viewsets.ModelViewSet):
    """
    Return information about task.
    """
    serializer_class = serializers.TaskSerializer
    permission_classes = (IsAuthenticated, )
    queryset = models.Task.objects.all()

    def create(self, request):
        """
        Submit a new task.
        """
        user = self.request.user
        task_serializer = serializers.TaskSerializer(data=request.data)
        task_serializer.is_valid(raise_exception=True)

        logging.info("Creating task")
        task = models.Task()
        task.user = user
        task.description = request.data.get("description", "")
        task.save()
        logging.info("Task created")

        return Response({"msg": "Task created"}, status=status.HTTP_201_CREATED)


    def list(self, request):
        """
        List all the tasks.
        """
        user = self.request.user
        qs = models.Task.objects.filter(user=user)
        task_serializer = serializers.TaskSerializer(qs, many=True)

        return Response(task_serializer.data, status=status.HTTP_200_OK)


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AccountCreateSerializer
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request, *args, **kwargs):
        """
        Create a new account.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(balance=0)
        logging.info("Account created")
        return Response({"msg": "Account created"}, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        return models.Account.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.AccountCreateSerializer
        return serializers.AccountSerializer
