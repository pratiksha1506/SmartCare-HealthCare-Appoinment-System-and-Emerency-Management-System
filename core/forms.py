from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from .models import User, PatientProfile, DoctorProfile


DAYS_OF_WEEK = (
    ('Mon', 'Monday'),
    ('Tue', 'Tuesday'),
    ('Wed', 'Wednesday'),
    ('Thu', 'Thursday'),
    ('Fri', 'Friday'),
    ('Sat', 'Saturday'),
    ('Sun', 'Sunday'),
)


class PatientRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150, required=True, label="Full Name", widget=forms.TextInput(attrs={'placeholder': 'e.g. John Doe', 'class': 'form-control'}))
    email = forms.EmailField(required=True, label="Email Address", widget=forms.EmailInput(attrs={'placeholder': 'john.doe@example.com', 'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'At least 6 characters', 'class': 'form-control'}), min_length=6, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm your password', 'class': 'form-control'}), label="Confirm Password")
    
    date_of_birth = forms.DateField(required=True, label="Date of Birth", widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    gender = forms.ChoiceField(choices=PatientProfile.GENDER_CHOICES, required=True, label="Gender", widget=forms.Select(attrs={'class': 'form-control'}))
    contact_number = forms.CharField(max_length=20, required=True, label="Contact Number", widget=forms.TextInput(attrs={'placeholder': '+1 555-0199', 'class': 'form-control'}))
    default_address = forms.CharField(max_length=255, required=False, label="Home Address (Optional)", widget=forms.TextInput(attrs={'placeholder': 'e.g. 12 Elm Street, Springfield', 'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['full_name', 'email', 'contact_number']

    def clean_email(self):
        email = self.cleaned_data.get('email').lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        email = self.cleaned_data['email']
        full_name = self.cleaned_data['full_name'].strip()
        names = full_name.split(' ', 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ''

        user = User.objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data['password'],
            first_name=first_name,
            last_name=last_name,
            role='patient',
            contact_number=self.cleaned_data['contact_number']
        )

        PatientProfile.objects.create(
            user=user,
            date_of_birth=self.cleaned_data['date_of_birth'],
            gender=self.cleaned_data['gender'],
            default_address=self.cleaned_data.get('default_address', '')
        )
        return user


class AdminDoctorCreationForm(forms.ModelForm):
    """
    Hospital Administrator form to onboard doctors.
    Only authorized administrators may create doctor accounts and profiles.
    """
    full_name = forms.CharField(
        max_length=150,
        required=True,
        label="Doctor Full Name",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Dr. Jane Smith', 'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        label="Doctor Email (Login Username)",
        widget=forms.EmailInput(attrs={'placeholder': 'dr.smith@smartcare.org', 'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Initial password for doctor login', 'class': 'form-control'}),
        min_length=6,
        label="Initial Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password', 'class': 'form-control'}),
        label="Confirm Password"
    )
    specialization = forms.ChoiceField(
        choices=DoctorProfile.SPECIALIZATION_CHOICES,
        required=True,
        label="Medical Specialization",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    qualification = forms.CharField(
        max_length=150,
        required=True,
        label="Medical Qualifications",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. MBBS, MD (Cardiology)', 'class': 'form-control'})
    )
    registration_number = forms.CharField(
        max_length=50,
        required=True,
        label="Medical Registration / License Number",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. MED-89420-NY', 'class': 'form-control'})
    )
    experience_years = forms.IntegerField(
        min_value=0,
        max_value=60,
        initial=5,
        label="Clinical Experience (Years)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    consultation_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=500.00,
        label="Consultation Fee ($)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    contact_number = forms.CharField(
        max_length=20,
        required=True,
        label="Doctor Contact Number",
        widget=forms.TextInput(attrs={'placeholder': '+1 (555) 0144', 'class': 'form-control'})
    )
    available_days_list = forms.MultipleChoiceField(
        choices=DAYS_OF_WEEK,
        initial=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'day-checkbox'}),
        label="Available Consultation Days"
    )
    work_start_time = forms.TimeField(
        initial="09:00:00",
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label="Daily Start Time"
    )
    work_end_time = forms.TimeField(
        initial="17:00:00",
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label="Daily End Time"
    )
    slot_duration_minutes = forms.IntegerField(
        min_value=10,
        max_value=120,
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Slot Duration (Minutes)"
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        label="Doctor Active Status (Available for patient bookings)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['full_name', 'email', 'contact_number']

    def clean_email(self):
        email = self.cleaned_data.get('email').lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean_registration_number(self):
        reg = self.cleaned_data.get('registration_number').strip()
        if DoctorProfile.objects.filter(registration_number=reg).exists():
            raise ValidationError("A doctor with this medical license/registration number already exists.")
        return reg

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        start_t = cleaned_data.get('work_start_time')
        end_t = cleaned_data.get('work_end_time')
        if start_t and end_t and start_t >= end_t:
            self.add_error('work_end_time', "Work end time must be after start time.")

        return cleaned_data

    def save(self, commit=True):
        email = self.cleaned_data['email'].lower().strip()
        full_name = self.cleaned_data['full_name'].strip()
        names = full_name.split(' ', 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ''

        with transaction.atomic():
            user = User.objects.create_user(
                username=email,
                email=email,
                password=self.cleaned_data['password'],
                first_name=first_name,
                last_name=last_name,
                role='doctor',
                contact_number=self.cleaned_data['contact_number']
            )

            selected_days = self.cleaned_data.get('available_days_list', ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
            days_str = ",".join(selected_days)
            start_t = self.cleaned_data.get('work_start_time')
            end_t = self.cleaned_data.get('work_end_time')
            summary = f"{selected_days[0]} - {selected_days[-1]}, {start_t.strftime('%I:%M %p')} - {end_t.strftime('%I:%M %p')}" if len(selected_days) > 1 else f"{days_str}, {start_t.strftime('%I:%M %p')} - {end_t.strftime('%I:%M %p')}"

            DoctorProfile.objects.create(
                user=user,
                specialization=self.cleaned_data['specialization'],
                qualification=self.cleaned_data['qualification'],
                registration_number=self.cleaned_data['registration_number'],
                experience_years=self.cleaned_data['experience_years'],
                hospital_name=getattr(settings, 'DEFAULT_HOSPITAL_NAME', 'SmartCare Central Hospital'),
                hospital_address=getattr(settings, 'DEFAULT_HOSPITAL_ADDRESS', '100 Healthcare Blvd, Metro City'),
                hospital_lat=getattr(settings, 'DEFAULT_HOSPITAL_LAT', 12.971598),
                hospital_lng=getattr(settings, 'DEFAULT_HOSPITAL_LNG', 77.594562),
                consultation_fee=self.cleaned_data['consultation_fee'],
                available_days=days_str,
                availability_summary=summary,
                work_start_time=start_t,
                work_end_time=end_t,
                slot_duration_minutes=self.cleaned_data.get('slot_duration_minutes', 30),
                is_active=self.cleaned_data.get('is_active', True)
            )
            return user


class DoctorAvailabilityForm(forms.ModelForm):
    """
    Allows doctors to manage their own schedule, consultation days, and active status.
    """
    available_days_list = forms.MultipleChoiceField(
        choices=DAYS_OF_WEEK,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'day-checkbox'}),
        label="Consultation Days"
    )
    work_start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label="Start Time"
    )
    work_end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label="End Time"
    )
    slot_duration_minutes = forms.IntegerField(
        min_value=10,
        max_value=120,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Consultation Slot Duration (Minutes)"
    )
    is_active = forms.BooleanField(
        required=False,
        label="Active (Accepting New Patient Appointments)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = DoctorProfile
        fields = ['work_start_time', 'work_end_time', 'slot_duration_minutes', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.available_days:
            self.fields['available_days_list'].initial = self.instance.available_days.split(',')

    def save(self, commit=True):
        profile = super().save(commit=False)
        selected_days = self.cleaned_data.get('available_days_list', [])
        profile.available_days = ",".join(selected_days)
        start_t = profile.work_start_time
        end_t = profile.work_end_time
        if selected_days:
            profile.availability_summary = f"{selected_days[0]} - {selected_days[-1]}, {start_t.strftime('%I:%M %p')} - {end_t.strftime('%I:%M %p')}" if len(selected_days) > 1 else f"{selected_days[0]}, {start_t.strftime('%I:%M %p')} - {end_t.strftime('%I:%M %p')}"
        if commit:
            profile.save()
        return profile


class RoleLoginForm(forms.Form):
    email = forms.CharField(
        label="Email Address",
        widget=forms.TextInput(attrs={'placeholder': 'Enter your registered email', 'class': 'form-control', 'autocomplete': 'username'})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password', 'class': 'form-control', 'autocomplete': 'current-password'})
    )

    def __init__(self, *args, target_role=None, **kwargs):
        self.target_role = target_role
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            clean_email = email.lower().strip()
            # Try authenticating directly with email or username
            user = authenticate(username=clean_email, password=password)
            if not user:
                user = authenticate(username=email.strip(), password=password)
            if not user:
                try:
                    matched = User.objects.get(email__iexact=clean_email)
                    user = authenticate(username=matched.username, password=password)
                except (User.DoesNotExist, User.MultipleObjectsReturned):
                    pass

            if not user:
                import logging
                logger = logging.getLogger('smartcare.auth')
                logger.warning("Authentication failed for identifier: %s", clean_email)
                raise ValidationError("Invalid email or password. Please check your credentials and try again.")

            if not user.is_active:
                raise ValidationError("This account has been deactivated. Please contact the hospital administrator.")

            # Validate role constraints
            if self.target_role == 'patient':
                if user.role != 'patient':
                    if user.role == 'doctor':
                        raise ValidationError("This portal is reserved for patients. Doctors must use the Doctor Login portal.")
                    elif user.is_admin or user.is_staff or user.is_superuser or user.role == 'admin':
                        raise ValidationError("This portal is reserved for patients. Administrators must use the Administrator Login portal.")
                    else:
                        raise ValidationError("This portal is reserved for patients. Please log in through your respective portal.")
            
            elif self.target_role == 'doctor':
                if user.role != 'doctor':
                    if user.role == 'patient':
                        raise ValidationError("This portal is reserved for doctors. Patients must use the Patient Login portal.")
                    elif user.is_admin or user.is_staff or user.is_superuser or user.role == 'admin':
                        raise ValidationError("This portal is reserved for doctors. Administrators must use the Administrator Login portal.")
                    else:
                        raise ValidationError("This portal is reserved for doctors. Please log in through your respective portal.")
                
                if not hasattr(user, 'doctor_profile'):
                    raise ValidationError("Doctor profile record not found. Please contact the hospital administrator.")
                if not user.doctor_profile.is_active:
                    raise ValidationError("Your doctor account has been deactivated. Please contact the hospital administrator.")

            elif self.target_role == 'admin':
                if not (user.role == 'admin' or user.is_staff or user.is_superuser):
                    if user.role == 'doctor':
                        raise ValidationError("Access Denied: This portal is reserved for hospital administrators. Doctors must use the Doctor Login portal.")
                    elif user.role == 'patient':
                        raise ValidationError("Access Denied: This portal is reserved for hospital administrators. Patients must use the Patient Login portal.")
                    else:
                        raise ValidationError("Access Denied: Only authorized hospital administrators can log in here.")

            self.user = user
        return cleaned_data


class LoginForm(RoleLoginForm):
    """General sign-in form compatible with all roles."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, target_role=None, **kwargs)


class AdminDoctorEditForm(forms.ModelForm):
    """
    Hospital Administrator form to edit an existing doctor's profile and credentials.
    """
    full_name = forms.CharField(
        max_length=150,
        required=True,
        label="Doctor Full Name",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        label="Doctor Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    contact_number = forms.CharField(
        max_length=20,
        required=True,
        label="Contact Number",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    available_days_list = forms.MultipleChoiceField(
        choices=DAYS_OF_WEEK,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'day-checkbox'}),
        label="Available Consultation Days"
    )

    class Meta:
        model = DoctorProfile
        fields = [
            'specialization',
            'qualification',
            'registration_number',
            'experience_years',
            'consultation_fee',
            'work_start_time',
            'work_end_time',
            'slot_duration_minutes',
            'is_active',
        ]
        widgets = {
            'specialization': forms.Select(attrs={'class': 'form-control'}),
            'qualification': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control'}),
            'consultation_fee': forms.NumberInput(attrs={'class': 'form-control'}),
            'work_start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'work_end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'slot_duration_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['full_name'].initial = user.get_full_name() or user.username
            self.fields['email'].initial = user.email
            self.fields['contact_number'].initial = user.contact_number
            if self.instance.available_days:
                self.fields['available_days_list'].initial = [d.strip() for d in self.instance.available_days.split(',') if d.strip()]

    def clean_email(self):
        email = self.cleaned_data.get('email').lower().strip()
        user_pk = self.instance.user.pk if self.instance and self.instance.pk else None
        if User.objects.filter(email=email).exclude(pk=user_pk).exists():
            raise ValidationError("Another user with this email address already exists.")
        return email

    def clean_registration_number(self):
        reg = self.cleaned_data.get('registration_number').strip()
        doc_pk = self.instance.pk if self.instance else None
        if DoctorProfile.objects.filter(registration_number=reg).exclude(pk=doc_pk).exists():
            raise ValidationError("Another doctor with this medical license/registration number already exists.")
        return reg

    def clean(self):
        cleaned_data = super().clean()
        start_t = cleaned_data.get('work_start_time')
        end_t = cleaned_data.get('work_end_time')
        if start_t and end_t and start_t >= end_t:
            self.add_error('work_end_time', "Work end time must be after start time.")
        return cleaned_data

    def save(self, commit=True):
        with transaction.atomic():
            profile = super().save(commit=False)
            user = profile.user
            full_name = self.cleaned_data['full_name'].strip()
            names = full_name.split(' ', 1)
            user.first_name = names[0]
            user.last_name = names[1] if len(names) > 1 else ''
            email = self.cleaned_data['email'].lower().strip()
            user.email = email
            user.username = email
            user.contact_number = self.cleaned_data['contact_number']
            user.save()

            selected_days = self.cleaned_data.get('available_days_list', [])
            profile.available_days = ",".join(selected_days)
            start_t = profile.work_start_time
            end_t = profile.work_end_time
            if selected_days:
                profile.availability_summary = (
                    f"{selected_days[0]} - {selected_days[-1]}, {start_t.strftime('%I:%M %p')} - {end_t.strftime('%I:%M %p')}"
                    if len(selected_days) > 1
                    else f"{selected_days[0]}, {start_t.strftime('%I:%M %p')} - {end_t.strftime('%I:%M %p')}"
                )
            if commit:
                profile.save()
            return profile


class AdminDoctorPasswordResetForm(forms.Form):
    """
    Hospital Administrator form to reset or set a temporary password for a doctor.
    """
    new_password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password (min 6 characters)'}),
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}),
        label="Confirm New Password"
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, user):
        new_password = self.cleaned_data['new_password']
        user.set_password(new_password)
        user.save()
        return user
