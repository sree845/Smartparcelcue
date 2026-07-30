from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from parcels.models import Booking, Slot


def make_slot(**overrides):
    now = timezone.now()
    defaults = {
        "name": "API Slot",
        "start_time": now + timedelta(hours=1),
        "end_time": now + timedelta(hours=2),
        "capacity": 1,
    }
    defaults.update(overrides)
    return Slot.objects.create(**defaults)


class SlotApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("gina", password="pw12345")
        self.staff = User.objects.create_user("henry", password="pw12345", is_staff=True)

    def test_anonymous_cannot_list_slots(self):
        response = self.client.get("/api/slots/")
        # DRF's SessionAuthentication doesn't issue a WWW-Authenticate
        # challenge, so an unauthenticated request is rejected with 403
        # rather than 401 here.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_non_staff_can_read_but_not_create(self):
        self.client.force_authenticate(self.user)
        make_slot()
        response = self.client.get("/api/slots/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        create_response = self.client.post(
            "/api/slots/",
            {
                "name": "New Slot",
                "start_time": timezone.now().isoformat(),
                "end_time": (timezone.now() + timedelta(hours=1)).isoformat(),
                "capacity": 3,
            },
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create_slot(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            "/api/slots/",
            {
                "name": "New Slot",
                "start_time": timezone.now().isoformat(),
                "end_time": (timezone.now() + timedelta(hours=1)).isoformat(),
                "capacity": 3,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class BookingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("ivy", password="pw12345")
        self.other_user = User.objects.create_user("jack", password="pw12345")
        self.slot = make_slot(capacity=1)

    def test_create_booking_fills_slot_and_hides_other_users_bookings(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/bookings/",
            {"parcel_name": "Package", "receiver_name": "Ivy", "slot": self.slot.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "Booked")

        # A second user should not see the first user's booking, and
        # should be blocked from booking the now-full slot.
        self.client.force_authenticate(self.other_user)
        list_response = self.client.get("/api/bookings/")
        self.assertEqual(list_response.data["count"], 0)

        conflict_response = self.client.post(
            "/api/bookings/",
            {"parcel_name": "Other package", "receiver_name": "Jack", "slot": self.slot.id},
        )
        self.assertEqual(conflict_response.status_code, status.HTTP_409_CONFLICT)

    def test_cancel_action(self):
        self.client.force_authenticate(self.user)
        create_response = self.client.post(
            "/api/bookings/",
            {"parcel_name": "Package", "receiver_name": "Ivy", "slot": self.slot.id},
        )
        booking_id = create_response.data["id"]
        cancel_response = self.client.post(f"/api/bookings/{booking_id}/cancel/")
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data["status"], "Cancelled")

    def test_non_staff_cannot_mark_delivered(self):
        self.client.force_authenticate(self.user)
        create_response = self.client.post(
            "/api/bookings/",
            {"parcel_name": "Package", "receiver_name": "Ivy", "slot": self.slot.id},
        )
        booking_id = create_response.data["id"]
        response = self.client.post(f"/api/bookings/{booking_id}/mark_delivered/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
