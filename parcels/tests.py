from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Slot


def make_slot(**overrides):
    now = timezone.now()
    defaults = {
        "name": "Evening Slot",
        "start_time": now + timedelta(hours=1),
        "end_time": now + timedelta(hours=2),
        "capacity": 1,
    }
    defaults.update(overrides)
    return Slot.objects.create(**defaults)


class SlotModelTests(TestCase):
    def test_available_true_when_under_capacity(self):
        slot = make_slot(capacity=2)
        self.assertTrue(slot.available)
        self.assertEqual(slot.booked_count, 0)

    def test_available_false_when_full(self):
        slot = make_slot(capacity=1)
        user = User.objects.create_user("alice", password="pw12345")
        Booking.objects.create(
            parcel_name="Box",
            receiver_name="Alice",
            start_time=slot.start_time,
            end_time=slot.end_time,
            slot=slot,
            user=user,
            status="Booked",
        )
        self.assertFalse(slot.available)

    def test_cancelled_bookings_dont_count_against_capacity(self):
        slot = make_slot(capacity=1)
        user = User.objects.create_user("bob", password="pw12345")
        Booking.objects.create(
            parcel_name="Box",
            receiver_name="Bob",
            start_time=slot.start_time,
            end_time=slot.end_time,
            slot=slot,
            user=user,
            status="Cancelled",
        )
        self.assertTrue(slot.available)


class RegisterParcelViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("carol", password="pw12345")
        self.client.login(username="carol", password="pw12345")
        self.slot = make_slot(capacity=1)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("register_parcel"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_booking_a_slot_creates_a_booked_booking(self):
        response = self.client.post(
            reverse("register_parcel"),
            {
                "parcel_name": "Textbook",
                "receiver_name": "Carol",
                "start_time": self.slot.start_time.isoformat(),
                "end_time": self.slot.end_time.isoformat(),
                "slot": self.slot.id,
            },
        )
        self.assertRedirects(response, reverse("my_parcels"))
        booking = Booking.objects.get(user=self.user)
        self.assertEqual(booking.status, "Booked")
        self.assertEqual(booking.slot, self.slot)

    def test_cannot_double_book_a_full_slot(self):
        other_user = User.objects.create_user("dave", password="pw12345")
        Booking.objects.create(
            parcel_name="Existing",
            receiver_name="Someone",
            start_time=self.slot.start_time,
            end_time=self.slot.end_time,
            slot=self.slot,
            user=other_user,
            status="Booked",
        )
        response = self.client.post(
            reverse("register_parcel"),
            {
                "parcel_name": "Textbook",
                "receiver_name": "Carol",
                "start_time": self.slot.start_time.isoformat(),
                "end_time": self.slot.end_time.isoformat(),
                "slot": self.slot.id,
            },
            follow=True,
        )
        self.assertEqual(
            Booking.objects.filter(user=self.user, status="Booked").count(), 0
        )
        messages = list(response.context["messages"])
        self.assertTrue(any("full" in str(m).lower() for m in messages))


class CancelParcelViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("erin", password="pw12345")
        self.client.login(username="erin", password="pw12345")
        self.slot = make_slot(capacity=1)
        self.booking = Booking.objects.create(
            parcel_name="Box",
            receiver_name="Erin",
            start_time=self.slot.start_time,
            end_time=self.slot.end_time,
            slot=self.slot,
            user=self.user,
            status="Booked",
        )

    def test_owner_can_cancel(self):
        self.client.post(reverse("cancel_parcel", args=[self.booking.id]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "Cancelled")

    def test_other_user_cannot_cancel(self):
        User.objects.create_user("frank", password="pw12345")
        self.client.login(username="frank", password="pw12345")
        response = self.client.post(reverse("cancel_parcel", args=[self.booking.id]))
        self.assertEqual(response.status_code, 404)
