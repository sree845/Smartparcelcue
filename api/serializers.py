from rest_framework import serializers

from parcels.models import Booking, Slot


class SlotSerializer(serializers.ModelSerializer):
    booked_count = serializers.IntegerField(read_only=True)
    available_capacity = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(source="available", read_only=True)

    class Meta:
        model = Slot
        fields = [
            "id",
            "name",
            "start_time",
            "end_time",
            "capacity",
            "is_auto_created",
            "booked_count",
            "available_capacity",
            "is_available",
        ]
        read_only_fields = ["is_auto_created"]

    def get_available_capacity(self, obj):
        return max(obj.capacity - obj.booked_count, 0)

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and start >= end:
            raise serializers.ValidationError("start_time must be before end_time.")
        return attrs


class BookingSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for a parcel booking.

    `user` is set from the authenticated request, not taken from the
    client payload, so a user can never create a booking on someone
    else's behalf.
    """

    user = serializers.ReadOnlyField(source="user.username")
    slot_detail = SlotSerializer(source="slot", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "parcel_name",
            "receiver_name",
            "start_time",
            "end_time",
            "status",
            "slot",
            "slot_detail",
            "user",
        ]
        read_only_fields = ["status", "start_time", "end_time"]

    # Note: slot-capacity validation intentionally lives in
    # BookingViewSet.create() (inside a select_for_update() transaction)
    # rather than here, so there is exactly one, race-safe place that
    # decides whether a slot is full and returns 409 Conflict.
