from django import forms
from .models import EmergencyPatient, PriorityAssessmentLog
from core.models import DoctorProfile, PatientProfile


class EmergencyRegistrationForm(forms.ModelForm):
    """
    Clinical Staff Intake Form.
    Only authorized clinical staff can register emergency patients and assign clinical priority.
    """
    full_name = forms.CharField(
        max_length=150,
        required=True,
        label="Emergency Patient Full Name",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Alex Morgan (or Unknown if unidentified)', 'class': 'form-control'})
    )
    age = forms.IntegerField(
        min_value=0,
        max_value=125,
        required=True,
        label="Patient Age",
        widget=forms.NumberInput(attrs={'placeholder': 'Age in years', 'class': 'form-control'})
    )
    gender = forms.ChoiceField(
        choices=EmergencyPatient.GENDER_CHOICES,
        required=True,
        label="Biological Sex / Gender",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    contact_number = forms.CharField(
        max_length=30,
        required=False,
        label="Next of Kin / Contact Number",
        widget=forms.TextInput(attrs={'placeholder': 'Emergency contact phone', 'class': 'form-control'})
    )
    priority_level = forms.ChoiceField(
        choices=EmergencyPatient.PRIORITY_CHOICES,
        initial=2,
        required=True,
        label="Clinical Triage Priority Level (Assigned by Clinical Staff)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    chief_complaint = forms.CharField(
        required=True,
        label="Chief Complaint / Incident Description",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe primary traumatic injury, acute symptoms, or presenting state...', 'class': 'form-control'})
    )
    triage_notes = forms.CharField(
        required=False,
        label="Clinical Triage Notes & Initial Observations",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Airway, Breathing, Circulation observations, pain score, initial conscious state...', 'class': 'form-control'})
    )
    patient_profile = forms.ModelChoiceField(
        queryset=PatientProfile.objects.select_related('user').all(),
        required=False,
        label="Link Registered Hospital Patient Profile (Optional)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    attending_clinician = forms.ModelChoiceField(
        queryset=DoctorProfile.objects.filter(is_active=True).select_related('user').all(),
        required=False,
        label="Assign Attending Clinician (Optional)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = EmergencyPatient
        fields = [
            'full_name',
            'age',
            'gender',
            'contact_number',
            'priority_level',
            'chief_complaint',
            'triage_notes',
            'patient_profile',
            'attending_clinician'
        ]


class PatientEmergencyReportForm(forms.Form):
    """
    Patient Symptom Reporting Form.
    Patients may report their symptoms, but they MUST NOT assign themselves a clinical priority.
    """
    symptoms = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe what you are currently experiencing (e.g. sudden severe pain, fever, injury)...', 'class': 'form-control'}),
        required=True,
        label="Describe Your Presenting Symptoms"
    )
    contact_phone = forms.CharField(
        max_length=30,
        required=True,
        label="Best Contact Phone",
        widget=forms.TextInput(attrs={'placeholder': 'Phone number where staff can reach you or your guardian', 'class': 'form-control'})
    )


class PriorityReassessmentForm(forms.Form):
    """
    Staff-Only Priority Reassessment Form.
    """
    new_priority = forms.ChoiceField(
        choices=EmergencyPatient.PRIORITY_CHOICES,
        required=True,
        label="New Clinical Priority",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    clinical_rationale = forms.CharField(
        required=True,
        label="Clinical Rationale for Priority Modification",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Mandatory justification: Describe change in physiological state or diagnostic findings...', 'class': 'form-control'})
    )
