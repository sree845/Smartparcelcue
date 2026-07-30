from django import forms
from .models import Booking

class BookingForm(forms.ModelForm):
    class Meta:
        model=Booking
        fields=['parcel_name','start_time','end_time']
        widgets={
            'start_time':forms.DateTimeInput(attrs={'type':'datetime-local'}),
            'end_time':forms.DateTimeInput(attrs={'type':'datetime-local'}),
        }
