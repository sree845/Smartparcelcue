from django.contrib import admin
from django import forms
from django.utils import timezone
from django.utils.html import format_html
from datetime import timedelta
from .models import Slot, Booking
class SlotForm(forms.ModelForm):
    repeat_days = forms.IntegerField(
        label="Repeat for how many days?",
        required=False,
        initial=1,
        min_value=1
    )
    class Meta:
        model=Slot
        fields=['name', 'start_time', 'end_time', 'capacity']
@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    form = SlotForm
    list_display=(
        'name',
        'slot_date',
        'start_time',
        'end_time',
        'capacity',
        'booked_count',
        'available',
        'last_adjusted_display',
    )
    list_editable=('capacity',)
    list_filter=('start_time', 'end_time')
    search_fields=('name',)
    def save_model(self, request, obj, form, change):
        if change:
            old_obj=Slot.objects.get(pk=obj.pk)
            if old_obj.capacity!=obj.capacity:
                obj.last_adjusted=timezone.now()
        else:
            obj.last_adjusted=timezone.now()
        repeat_days=form.cleaned_data.get('repeat_days') or 1
        start=obj.start_time
        end=obj.end_time
        for i in range(repeat_days):
            if i>0:
                obj.pk=None
                obj.start_time=start+timedelta(days=i)
                obj.end_time=end+timedelta(days=i)
            super().save_model(request, obj, form, change)
    def booked_count(self, obj):
        return Booking.objects.filter(slot=obj).count()
    booked_count.short_description="Booked Count"
    def available(self, obj):
        booked = Booking.objects.filter(slot=obj).count()
        return max(obj.capacity - booked, 0)
    available.short_description = "Available"
    def slot_date(self, obj):
        return obj.start_time.date()
    slot_date.short_description = 'Date'
    def last_adjusted_display(self, obj):
        if hasattr(obj, 'last_adjusted') and obj.last_adjusted:
            if timezone.now() - obj.last_adjusted<timedelta(hours=24):
                return format_html(
                    '<span style="color:green; font-weight:bold;">Recently Adjusted</span><br>'
                    '<small>{}</small>',
                    obj.last_adjusted.strftime("%Y-%m-%d %H:%M")
                )
            else:
                return obj.last_adjusted.strftime("%Y-%m-%d %H:%M")
        return "—"
    last_adjusted_display.short_description = "Last Adjusted"
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display=('parcel_name', 'receiver_name', 'slot', 'status', 'user', 'start_time')
    list_filter=('status', 'slot')
    search_fields=('parcel_name', 'receiver_name', 'user__username')
    list_editable=('status',)
    actions = ['mark_delivered']
    def save_model(self, request, obj, form, change):
        obj.status=obj.status.capitalize()
        super().save_model(request, obj, form, change)
    def mark_delivered(self, request, queryset):
        """Mark selected bookings as delivered."""
        queryset.update(status='Delivered')
    mark_delivered.short_description = "Mark selected parcels as Delivered"
    def response_post_save_change(self, request, obj):
        """Return to slot list for refreshed counts."""
        if "_continue" not in request.POST:
            from django.urls import reverse
            from django.shortcuts import redirect
            return redirect(reverse('admin:parcels_slot_changelist'))
        return super().response_post_save_change(request, obj)
