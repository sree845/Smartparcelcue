from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Count
from .models import Slot, Booking
import random
BOOKED_STATUSES = ['Booked', 'Auto-Assigned', 'Rescheduled']
def register(request):
    if request.method=='POST':
        form=UserCreationForm(request.POST)
        if form.is_valid():
            user=form.save()
            auth_login(request,user)
            messages.success(request,"Registration successful.")
            return redirect('home')
        else:
            messages.error(request,"Invalid registration details.")
    else:
        form=UserCreationForm()
    return render(request,'parcels/register.html',{'form':form})
def login_view(request):
    if request.method=='POST':
        form=AuthenticationForm(request,data=request.POST)
        if form.is_valid():
            auth_login(request,form.get_user())
            return redirect('home')
        else:
            messages.error(request,"Invalid username or password.")
    else:
        form=AuthenticationForm()
    return render(request,'parcels/login.html',{'form':form})
def logout_view(request):
    auth_logout(request)
    return redirect('login')
def home(request):
    return render(request,'parcels/home.html')
def slot_current_bookings(slot):
    return Booking.objects.filter(slot=slot, status__in=BOOKED_STATUSES).count()
def slots_in_range(start_time,end_time):
    return Slot.objects.filter(start_time__lt=end_time, end_time__gt=start_time).order_by('start_time')
def auto_assign_slot_existing_only(start_time, end_time):
    if not (start_time and end_time):
        return None
    slots=list(slots_in_range(start_time,end_time))
    if not slots:
        return None
    available=[]
    for s in slots:
        bookings_count=slot_current_bookings(s)
        remaining=s.capacity-bookings_count
        if remaining>0:
            available.append(s)
    if available:
        return random.choice(available)
    chosen=random.choice(slots)
    chosen.capacity=chosen.capacity + 1
    chosen.save(update_fields=['capacity'])
    return chosen
@login_required
def register_parcel(request):
    available_slots=[]
    no_slots=False
    parcel_name=receiver_name=start_time_str=end_time_str=''
    if request.method=='POST':
        parcel_name=request.POST.get('parcel_name','').strip()
        receiver_name=request.POST.get('receiver_name','').strip()
        start_time_str=request.POST.get('start_time','')
        end_time_str=request.POST.get('end_time','')
        try:
            start_time=parse_datetime(start_time_str)
            end_time=parse_datetime(end_time_str)
        except Exception:
            messages.error(request,"Invalid date/time format.")
            return redirect('register_parcel')
        if not start_time or not end_time or start_time>=end_time:
            messages.error(request,"Please select valid start and end times.")
            return redirect('register_parcel')
        if 'check_slots' in request.POST:
            available_slots=[]
            for slot in slots_in_range(start_time,end_time):
                booked_count=slot_current_bookings(slot)
                remaining=slot.capacity-booked_count
                if remaining>0:
                    available_slots.append({'slot':slot, 'remaining':remaining})
            if not available_slots:
                no_slots=True
            return render(request,'parcels/register_parcel.html', {
                'available_slots': available_slots,
                'no_slots': no_slots,
                'parcel_name': parcel_name,
                'receiver_name': receiver_name,
                'start_time': start_time_str,
                'end_time': end_time_str
            })
        if request.POST.get('slot'):
            slot_id = request.POST.get('slot')
            slot = get_object_or_404(Slot, id=slot_id)
            with transaction.atomic():
                slot_for_update = Slot.objects.select_for_update().get(pk=slot.pk)
                booked = Booking.objects.filter(slot=slot_for_update, status__in=BOOKED_STATUSES).count()
                if booked >= slot_for_update.capacity:
                    messages.error(request, "Selected slot is full.")
                    return redirect('register_parcel')
                Booking.objects.create(
                    parcel_name=parcel_name,
                    receiver_name=receiver_name,
                    user=request.user,
                    slot=slot_for_update,
                    start_time=slot_for_update.start_time,
                    end_time=slot_for_update.end_time,
                    status='Booked'
                )
            messages.success(request, f"Parcel '{parcel_name}' booked successfully in selected slot.")
            return redirect('my_parcels')
        if 'auto_assign' in request.POST:
            chosen_slot = auto_assign_slot_existing_only(start_time, end_time)
            if not chosen_slot:
                messages.error(request, "No existing overlapping slots to auto-assign.")
                return redirect('register_parcel')
            with transaction.atomic():
                slot_for_update = Slot.objects.select_for_update().get(pk=chosen_slot.pk)
                booked = Booking.objects.filter(slot=slot_for_update, status__in=BOOKED_STATUSES).count()
                if booked >= slot_for_update.capacity:
                    messages.error(request, "Slot became full while trying to auto-assign. Try again.")
                    return redirect('register_parcel')
                Booking.objects.create(
                    parcel_name=parcel_name,
                    receiver_name=receiver_name,
                    user=request.user,
                    slot=slot_for_update,
                    start_time=slot_for_update.start_time,
                    end_time=slot_for_update.end_time,
                    status='Auto-Assigned'
                )
            messages.success(request, f"Parcel '{parcel_name}' auto-assigned to slot starting at {slot_for_update.start_time}.")
            return redirect('my_parcels')
    return render(request, 'parcels/register_parcel.html', {
        'available_slots': available_slots,
        'no_slots': no_slots,
        'parcel_name': parcel_name,
        'receiver_name': receiver_name,
        'start_time': start_time_str,
        'end_time': end_time_str
    })
@login_required
def my_parcels(request):
    parcels = Booking.objects.filter(user=request.user).order_by('-id')
    return render(request, 'parcels/my_parcels.html', {'parcels': parcels})
@login_required
def cancel_parcel(request, parcel_id):
    booking = get_object_or_404(Booking, id=parcel_id, user=request.user)
    if booking.status=="Cancelled":
        messages.info(request, "This booking is already cancelled.")
        return redirect('my_parcels')
    booking.status = "Cancelled"
    booking.save()
    messages.success(request, f"Booking '{booking.parcel_name}' has been cancelled.")
    return redirect('my_parcels')
@login_required
def reschedule_parcel(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    all_slots = Slot.objects.all().order_by('start_time')
    if request.method == "POST":
        new_slot_id = request.POST.get("slot_id")
        if not new_slot_id:
            messages.error(request, "Please select a valid slot.")
            return redirect("reschedule_parcel", booking_id=booking.id)
        new_slot = get_object_or_404(Slot, id=new_slot_id)
        with transaction.atomic():
            new_slot_for_update = Slot.objects.select_for_update().get(pk=new_slot.pk)
            if Booking.objects.filter(slot=new_slot_for_update, status__in=BOOKED_STATUSES).count() >= new_slot_for_update.capacity:
                messages.error(request, "Selected slot is already full.")
                return redirect("reschedule_parcel", booking_id=booking.id)
            booking.slot = new_slot_for_update
            booking.start_time=new_slot_for_update.start_time
            booking.end_time=new_slot_for_update.end_time
            booking.status="Rescheduled"
            booking.save()
        messages.success(request, f"Parcel '{booking.parcel_name}' rescheduled.")
        return redirect("my_parcels")
    return render(request, "parcels/reschedule_parcel.html", {
        "booking": booking,
        "available_slots": all_slots,
    })
@login_required
def update_status(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if not request.user.is_staff and booking.user != request.user:
        messages.error(request, "You are not allowed to update this booking.")
        return redirect('my_parcels')
    booking.status = "Delivered"
    booking.save()
    messages.success(request, f"Parcel '{booking.parcel_name}' marked as Delivered.")
    return redirect('home' if request.user.is_staff else 'my_parcels')
