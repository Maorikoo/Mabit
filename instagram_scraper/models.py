from django.db import models
import uuid
from django.utils import timezone

# Create your models here.

class InstagramUser(models.Model):
    username = models.CharField(max_length=50, unique=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    is_private = models.BooleanField(default=True)
    last_scraped = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.username

class InstagramStory(models.Model):
    username = models.ForeignKey(InstagramUser,on_delete=models.CASCADE,related_name="stories")
    story_id = models.CharField(max_length=100, unique=True)
    media_url = models.URLField()
    media_file = models.FileField(upload_to='stories/', blank=True, null=True)
    media_type = models.CharField(max_length=20,choices=[("image", "Image"), ("video", "Video")])
    timestamp = models.DateTimeField()

    def __str__(self):
        # Format timestamp to match filename format: dd.mm.yy_HH.MM
        ts_str = self.timestamp.strftime("%d.%m.%y_%H.%M")
        return f"{self.username.username}-{ts_str}-{self.story_id}"

    class Meta:
        verbose_name = "Instagram Story"
        verbose_name_plural = "Instagram Stories"