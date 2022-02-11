from rest_framework.viewsets import mixins, GenericViewSet

from django.db.models import Q

from maipassport.core.api_pagination import WebApiPageNumberPagination
from maipassport.records.serializers import (WebApproachRecordSerializer, WebPlaceRecordSerializer,
                                             WebClockInRecordSerializer, WebCompanyRegSerializer, WebShopRegSerializer,
                                             WebVacRecordSerializer, WebCovHistorySerializer, WebRapTestSerializer)
from maipassport.records.models import (ApproachRecord, PlaceEntryRecord, AttendanceRecord, VacRecord,
                                        RapidTestRecord, CovidHistoryRecord)
from maipassport.companies.models import NewCompanyApply, Place


class WebUserRecordViewSet(mixins.ListModelMixin, GenericViewSet):

    lookup_field = 'pub_id'
    pagination_class = WebApiPageNumberPagination

    def get_queryset(self):
        if self.action == 'list':
            if 'record_type' in self.request.query_params:
                record_type = self.request.query_params['record_type']
                if record_type == 'APPROACH':
                    queryset = (
                        # ApproachRecord.objects
                        #     .filter(user=self.request.user_object)
                        ApproachRecord.objects
                            .select_related('healthrecord', 'visitorregistration')
                            .filter(
                            Q(app_user=self.request.user_object) |
                            Q(scan_user=self.request.user_object)
                        ).order_by('-created')
                    )
                elif record_type == 'PLACE':
                    queryset = (
                        PlaceEntryRecord.objects
                            .filter(app_user=self.request.user_object).order_by('-created')
                    )
                elif record_type == 'CLOCK_IN':
                    queryset = (
                        AttendanceRecord.objects
                            .filter(app_user=self.request.user_object).order_by('-created')
                    )
                elif record_type == 'COM_REG':
                    queryset = (
                        NewCompanyApply.objects
                            .filter(apply_user=self.request.user_object).order_by('-created')
                    )
                elif record_type == 'SHOP_REG':
                    queryset = (
                        Place.objects
                            .filter(place_user=self.request.user_object).order_by('-created')
                    )
                elif record_type == 'VAC_RECORD':
                    queryset = (
                        VacRecord.objects
                            .filter(app_user=self.request.user_object).order_by('-created')
                    )
                elif record_type == 'RAP_TEST':
                    queryset = (
                        RapidTestRecord.objects
                            .filter(app_user=self.request.user_object).order_by('-created')
                    )
                elif record_type == 'COV_HISTORY':
                    queryset = (
                        CovidHistoryRecord.objects
                            .filter(app_user=self.request.user_object).order_by('-created')
                    )
                else:
                    raise NotImplementedError
            else:
                # queryset = queryset.none()
                raise NotImplementedError
        else:
            raise NotImplementedError
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            if 'record_type' in self.request.query_params:
                if self.request.query_params['record_type'] == 'APPROACH':
                    return WebApproachRecordSerializer
                elif self.request.query_params['record_type'] == 'PLACE':
                    return WebPlaceRecordSerializer
                elif self.request.query_params['record_type'] == 'CLOCK_IN':
                    return WebClockInRecordSerializer
                elif self.request.query_params['record_type'] == 'COM_REG':
                    return WebCompanyRegSerializer
                elif self.request.query_params['record_type'] == 'SHOP_REG':
                    return WebShopRegSerializer
                elif self.request.query_params['record_type'] == 'VAC_RECORD':
                    return WebVacRecordSerializer
                elif self.request.query_params['record_type'] == 'RAP_TEST':
                    return WebRapTestSerializer
                elif self.request.query_params['record_type'] == 'COV_HISTORY':
                    return WebCovHistorySerializer
        else:
            raise NotImplementedError

