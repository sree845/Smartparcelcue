from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from parcels.models import Booking, Slot

from .serializers import BookingSerializer, SlotSerializer

BOOKED_STATUSES = ["Booked", "Approved", "Auto-Assigned", "Rescheduled"]


class IsStaffOrReadOnly(permissions.BasePermission):
    """Anyone authenticated can view slots; only staff can create/edit them."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class SlotViewSet(viewsets.ModelViewSet):
    """
    /api/slots/            -> list / create delivery slots
    /api/slots/{id}/       -> retrieve / update / delete a slot
    /api/slots/?date=...   -> filter by date range via query params (see filterset)
    """

    queryset = Slot.objects.all().order_by("start_time")
    serializer_class = SlotSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_fields = ["name"]


class BookingViewSet(viewsets.ModelViewSet):
    """
    /api/bookings/              -> list the current user's bookings, or all
                                    bookings if the requester is staff
    /api/bookings/               (POST) -> book a slot, race-safe
    /api/bookings/{id}/cancel/  (POST) -> cancel a booking
    """

    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status", "slot"]

    def get_queryset(self):
        qs = Booking.objects.select_related("slot", "user").order_by("-id")
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slot = serializer.validated_data.get("slot")

        if slot is None:
            # No specific slot requested -> defer to the model defaults.
            booking = serializer.save(user=request.user, status="Pending")
            return Response(
                self.get_serializer(booking).data, status=status.HTTP_201_CREATED
            )

        # Guard against two requests racing for the last seat in a slot,
        # mirroring the transaction.atomic()/select_for_update() pattern
        # already used in parcels/views.py for the HTML flow.
        with transaction.atomic():
            locked_slot = Slot.objects.select_for_update().get(pk=slot.pk)
            already_booked = Booking.objects.filter(
                slot=locked_slot, status__in=BOOKED_STATUSES
            ).count()
            if already_booked >= locked_slot.capacity:
                return Response(
                    {"slot": "This slot just filled up. Please pick another."},
                    status=status.HTTP_409_CONFLICT,
                )
            booking = serializer.save(
                user=request.user,
                slot=locked_slot,
                start_time=locked_slot.start_time,
                end_time=locked_slot.end_time,
                status="Booked",
            )

        return Response(
            self.get_serializer(booking).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status == "Cancelled":
            return Response({"detail": "Already cancelled."}, status=status.HTTP_200_OK)
        booking.status = "Cancelled"
        booking.save(update_fields=["status"])
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def mark_delivered(self, request, pk=None):
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff can mark parcels as delivered."},
                status=status.HTTP_403_FORBIDDEN,
            )
        booking = self.get_object()
        booking.status = "Delivered"
        booking.save(update_fields=["status"])
        return Response(self.get_serializer(booking).data)
