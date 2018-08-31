from cccatalog.api.serializers.list_serializers import \
    ImageListCreateSerializer, ImageListResponseSerializer, \
    ImageListUpdateSerializer
from django.forms.models import model_to_dict
from cccatalog.api.models import ImageList
from cccatalog.api.utils.throttle import PostRequestThrottler
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import throttle_classes
from rest_framework.response import Response
from rest_framework.reverse import reverse


class _List(GenericAPIView):
    serializer_class = ImageListCreateSerializer
    queryset = ImageList.objects.all()
    lookup_field = 'id'


class _CreateResponse(serializers.Serializer):
    url = serializers.HyperlinkedRelatedField(
        view_name='list-detail',
        read_only=True,
        help_text="The URL of the new list."
    )
    auth = serializers.CharField(
        help_text="A 64 character authorization code used to prove ownership of"
                  " a list. Add this to the authorization header when updating "
                  "or deleting lists."
    )


class CreateList(_List):

    @swagger_auto_schema(operation_id="list_create",
                         responses={
                             201: _CreateResponse,
                             400: "Bad Request"
                         })
    @throttle_classes([PostRequestThrottler])
    def post(self, request, format=None):
        """
        Create a public collection of images. Returns the ID of the newly
        created list.

        To prevent abuse, only up to 30 lists can be made by a single user per
        day, and lists can only contain up to 500 items. Additionally, all
        input primary keys must be valid. If any of these constraints are
        violated, a validation error is returned.
        """
        serialized = ImageListCreateSerializer(data=request.data)
        if not serialized.is_valid():
            return Response(
                status=400,
                data=serialized.errors
            )

        _list = serialized.save()
        url = request.build_absolute_uri(reverse('list-detail', [_list.slug]))
        return Response(
            status=201,
            data={
                'url': url,
                'auth': _list.auth
            }
        )


class ListDetail(_List, RetrieveModelMixin):
    @swagger_auto_schema(operation_id="list_detail",
                         responses={
                             200: ImageListResponseSerializer,
                             404: 'Not Found'
                         })
    def get(self, request, slug, format=None):
        """ Get the details of a single list. """
        try:
            _list = ImageList.objects.get(slug=slug)
        except ImageList.DoesNotExist:
            return Response(status=404)
        resolved = {
            'id': slug,
            'images': [model_to_dict(x) for x in _list.images.all()]
        }
        return Response(status=200, data=resolved)

    @staticmethod
    def _authenticated(list_model, request):
        return list_model.auth == \
               request.META['HTTP_AUTHORIZATION'].split(' ')[1]

    @swagger_auto_schema(operation_id="list_delete",
                         security=[
                             {
                                 "anonymous_list": {
                                     "type": "basic"
                                 }
                             }
                         ],
                         responses={
                             204: '',
                             403: 'Forbidden',
                             404: 'Not Found'
                         })
    def delete(self, request, slug, format=None):
        try:
            _list = ImageList.objects.get(slug=slug)
        except ImageList.DoesNotExist:
            return Response(status=404)
        if self._authenticated(_list, request):
            _list.delete()
            return Response(status=204)
        else:
            return Response(status=403)

    def put(self, request, slug, format=None):
        """ Update the contents of a list. """
        serialized = ImageListUpdateSerializer(data=request.data)
        if not serialized.is_valid():
            return Response(
                status=400,
                data=serialized.errors
            )

        try:
            _list = ImageList.objects.get(slug=slug)
        except ImageList.DoesNotExist:
            return Response(status=404)
        supplied_auth = request.META['HTTP_AUTHORIZATION'].split(' ')[1]
        if self._authenticated(_list, request):
            _list.images.clear()
            _list.images.add(*serialized.validated_data['images'])
            return Response(status=204)
        else:
            return Response(status=403)

