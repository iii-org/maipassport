from django.forms import ModelForm
from maipassport.records.models import VacRecord, CovidHistoryRecord, RapidTestRecord

class UploadVacImage(ModelForm):
    class Meta:
        model = VacRecord
        fields = ['image']


class UploadCovidImage(ModelForm):
    class Meta:
        model = CovidHistoryRecord
        fields = ['image']


class UploadRapidImage(ModelForm):
    class Meta:
        model = RapidTestRecord
        fields = ['image']

