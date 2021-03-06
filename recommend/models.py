from django.db import models
from django.forms import ModelForm
from django.contrib.auth.models import User

MAX_RATING_VALUE = 5
DEFAULT_RECOMMENDATION_TYPE = "for-you"

# Create your models here.
class Rating(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    #user_id = models.BigIntegerField(default=0) # DEPRECATED
    subject_id = models.CharField(max_length=50)
    value = models.IntegerField(default=0)

    def __str__(self):
        return "User {} rated {} as {}".format(self.user_id, self.subject_id, self.value)

class Recommendation(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    #user_id = models.BigIntegerField(default=0) # DEPRECATED
    rec_type = models.CharField(max_length=20)
    subjects = models.CharField(max_length=500)

    def __str__(self):
        return "Recommendation ({}) for user {}: {}".format(self.rec_type, self.user_id, self.subjects)
