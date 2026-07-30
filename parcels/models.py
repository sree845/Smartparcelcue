from django.db import models
from django.contrib.auth.models import User
class Slot(models.Model):
    name=models.CharField(max_length=50)  
    start_time=models.DateTimeField()    
    end_time=models.DateTimeField()       
    capacity=models.PositiveIntegerField(default=1) 
    is_auto_created = models.BooleanField(default=False) 
    @property
    def booked_count(self):
        return self.bookings.filter(status__in=['Booked', 'Approved']).count()
    @property
    def available(self):
        return self.booked_count<self.capacity
    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"
class Booking(models.Model):
    STATUS_CHOICES=[
        ('Pending','Pending'),     
        ('Booked','Booked'),        
        ('Approved','Approved'),    
        ('Delivered','Delivered'),   
        ('Cancelled','Cancelled'),  
        ('Rescheduled','Rescheduled'), 
        ('Completed','Completed'),
    ]
    parcel_name=models.CharField(max_length=100)    
    receiver_name=models.CharField(max_length=100) 
    start_time=models.DateTimeField()              
    end_time=models.DateTimeField()              
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default="Pending")
    slot=models.ForeignKey(
        Slot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )  
    user=models.ForeignKey(User,on_delete=models.CASCADE) 
    def __str__(self):
        return f"{self.parcel_name} - {self.status}"
    def save(self,*args,**kwargs):
        try:
            old=Booking.objects.get(pk=self.pk) 
        except Booking.DoesNotExist:
            old=None
        super().save(*args,**kwargs)
