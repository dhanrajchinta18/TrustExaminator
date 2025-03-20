from django.db import models
from django.contrib.auth.models import AbstractUser
import datetime
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone  # Import timezone for time-aware datetimes

def teacherID():
    t_id = 'TEA-1'
    try:
        prev = CustomUser.objects.values('teacher_id').last()
        prev = prev['teacher_id']
        number = prev.split('-')[1]
        number = int(number) + 1
        t_id = 'TEA-' + str(number)
    except:
        t_id = 'TEA-1'
    return t_id

ROLE = (
    ('teacher','teacher'),
    ('coe','coe'),
    ('superintendent','superintendent')
)
SEM = (
    ('None','None'),
    ('I','I'),
    ('II','II'),
    ('III','III'),
    ('IV','IV'),
    ('V','V'),
    ('VI','VI'),
    ('VII','VII'),
    ('VIII','VIII')
)
BRANCH = (
    ('None','None'),
    ('CSE','CSE'),
    ('IT','IT'),
    ('ECE','ECE'),
    ('EEE','EEE'),
    ('MECH','MECH'),
    ('BioTech','BioTech')
)
SUB = (
    ('None','None'),
    ('Compiler Design','Compiler Design'),
    ('Digital Signal Processing','Digital Signal Processing'),
    ('Cloud Computing','Cloud Computing'),
    ('Agile Development','Agile Development')
)
STATUS = (
    ('Pending','Pending'),
    ('Accepted','Accepted'),
    ('Uploaded','Uploaded'),
    ('Finalized','Finalized')
)

class CustomUser(AbstractUser):
    teacher_id = models.CharField(max_length=20, default=teacherID, blank=True)
    course = models.CharField(max_length=4, choices=(('None','None'), ('B.E.',"B.E."), ('M.E.','M.E.')), default='None')
    semester = models.CharField(max_length=4, choices=SEM, default='None')
    branch = models.CharField(max_length=40, choices=BRANCH, default='None')
    subject = models.CharField(max_length=30, choices=SUB, default='None')
    role = models.CharField(max_length=20, choices=ROLE, default='teacher')

    def __str__(self):
        return self.username

class Request(models.Model):
    tusername = models.CharField(max_length=40, default='None')
    s_code = models.CharField(max_length=7, default="None")
    syllabus = models.FileField(default=None)
    q_pattern = models.FileField(default=None)
    # Replace the single deadline with two DateTimeFields:
    paper_deadline = models.DateTimeField(null=True, blank=True)  # Paper submission deadline
    exam_time = models.DateTimeField(null=True, blank=True)       # Exam timing
    status = models.CharField(max_length=25, default='Pending')
    enc_field = ArrayField(models.BinaryField(max_length=500, default=None), default=list)
    private_key = models.FileField(default=None)
    encrypted_file = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.tusername

class FinalPapers(models.Model):
    s_code = models.CharField(max_length=7, default="None")
    course = models.CharField(max_length=4, default='None')
    semester = models.CharField(max_length=4, default='None')
    branch = models.CharField(max_length=40, default='None')
    subject = models.CharField(max_length=30, default='None')
    paper = models.FileField(default=None)
    blockchain_status = models.CharField(max_length=20, default="Pending")
    tx_hash = models.CharField(max_length=100, blank=True, null=True)
    download_tx_hash = models.CharField(max_length=100, blank=True, null=True,help_text="Blockchain transaction hash for the download event.")

    def __str__(self):
        return self.s_code

class SubjectCode(models.Model):
    s_code = models.CharField(max_length=7)
    subject = models.CharField(max_length=40)

    def __str__(self):
        return self.subject