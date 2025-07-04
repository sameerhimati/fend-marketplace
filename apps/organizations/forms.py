from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.conf import settings
from .models import Organization, PilotDefinition, PartnerPromotion
from .validators import clean_and_validate_website, validate_industry_tags
from datetime import datetime

User = get_user_model()

class OrganizationBasicForm(forms.ModelForm):
    # Add user fields
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    
    # Add contact fields for all organization types
    primary_contact_name = forms.CharField(max_length=255, required=True)
    primary_contact_phone = forms.CharField(max_length=20, required=True)
    
    # Industry tags for better matching
    industry_tags = forms.CharField(
        max_length=300,
        required=False,
        help_text="Enter industry tags separated by commas (e.g., AI/ML, FinTech, SaaS)",
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., AI/ML, FinTech, SaaS, Cybersecurity',
            'class': 'shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md'
        })
    )
    country_code = forms.ChoiceField(choices = [
        ('+1', 'United States (+1)'),
        ('+1', 'Canada (+1)'),
        ('+93', 'Afghanistan (+93)'),
        ('+355', 'Albania (+355)'),
        ('+213', 'Algeria (+213)'),
        ('+376', 'Andorra (+376)'),
        ('+244', 'Angola (+244)'),
        ('+54', 'Argentina (+54)'),
        ('+374', 'Armenia (+374)'),
        ('+61', 'Australia (+61)'),
        ('+43', 'Austria (+43)'),
        ('+994', 'Azerbaijan (+994)'),
        ('+973', 'Bahrain (+973)'),
        ('+880', 'Bangladesh (+880)'),
        ('+375', 'Belarus (+375)'),
        ('+32', 'Belgium (+32)'),
        ('+501', 'Belize (+501)'),
        ('+229', 'Benin (+229)'),
        ('+975', 'Bhutan (+975)'),
        ('+591', 'Bolivia (+591)'),
        ('+387', 'Bosnia and Herzegovina (+387)'),
        ('+267', 'Botswana (+267)'),
        ('+55', 'Brazil (+55)'),
        ('+673', 'Brunei (+673)'),
        ('+359', 'Bulgaria (+359)'),
        ('+226', 'Burkina Faso (+226)'),
        ('+257', 'Burundi (+257)'),
        ('+855', 'Cambodia (+855)'),
        ('+237', 'Cameroon (+237)'),
        ('+238', 'Cape Verde (+238)'),
        ('+236', 'Central African Republic (+236)'),
        ('+235', 'Chad (+235)'),
        ('+56', 'Chile (+56)'),
        ('+86', 'China (+86)'),
        ('+57', 'Colombia (+57)'),
        ('+269', 'Comoros (+269)'),
        ('+242', 'Congo (+242)'),
        ('+506', 'Costa Rica (+506)'),
        ('+385', 'Croatia (+385)'),
        ('+53', 'Cuba (+53)'),
        ('+357', 'Cyprus (+357)'),
        ('+420', 'Czech Republic (+420)'),
        ('+45', 'Denmark (+45)'),
        ('+253', 'Djibouti (+253)'),
        ('+593', 'Ecuador (+593)'),
        ('+20', 'Egypt (+20)'),
        ('+503', 'El Salvador (+503)'),
        ('+240', 'Equatorial Guinea (+240)'),
        ('+291', 'Eritrea (+291)'),
        ('+372', 'Estonia (+372)'),
        ('+251', 'Ethiopia (+251)'),
        ('+679', 'Fiji (+679)'),
        ('+358', 'Finland (+358)'),
        ('+33', 'France (+33)'),
        ('+241', 'Gabon (+241)'),
        ('+220', 'Gambia (+220)'),
        ('+995', 'Georgia (+995)'),
        ('+49', 'Germany (+49)'),
        ('+233', 'Ghana (+233)'),
        ('+30', 'Greece (+30)'),
        ('+502', 'Guatemala (+502)'),
        ('+224', 'Guinea (+224)'),
        ('+592', 'Guyana (+592)'),
        ('+509', 'Haiti (+509)'),
        ('+504', 'Honduras (+504)'),
        ('+852', 'Hong Kong (+852)'),
        ('+36', 'Hungary (+36)'),
        ('+354', 'Iceland (+354)'),
        ('+91', 'India (+91)'),
        ('+62', 'Indonesia (+62)'),
        ('+98', 'Iran (+98)'),
        ('+964', 'Iraq (+964)'),
        ('+353', 'Ireland (+353)'),
        ('+972', 'Israel (+972)'),
        ('+39', 'Italy (+39)'),
        ('+225', 'Ivory Coast (+225)'),
        ('+876', 'Jamaica (+876)'),
        ('+81', 'Japan (+81)'),
        ('+962', 'Jordan (+962)'),
        ('+7', 'Kazakhstan (+7)'),
        ('+254', 'Kenya (+254)'),
        ('+965', 'Kuwait (+965)'),
        ('+996', 'Kyrgyzstan (+996)'),
        ('+856', 'Laos (+856)'),
        ('+371', 'Latvia (+371)'),
        ('+961', 'Lebanon (+961)'),
        ('+266', 'Lesotho (+266)'),
        ('+231', 'Liberia (+231)'),
        ('+218', 'Libya (+218)'),
        ('+423', 'Liechtenstein (+423)'),
        ('+370', 'Lithuania (+370)'),
        ('+352', 'Luxembourg (+352)'),
        ('+853', 'Macau (+853)'),
        ('+389', 'Macedonia (+389)'),
        ('+261', 'Madagascar (+261)'),
        ('+265', 'Malawi (+265)'),
        ('+60', 'Malaysia (+60)'),
        ('+960', 'Maldives (+960)'),
        ('+223', 'Mali (+223)'),
        ('+356', 'Malta (+356)'),
        ('+692', 'Marshall Islands (+692)'),
        ('+222', 'Mauritania (+222)'),
        ('+230', 'Mauritius (+230)'),
        ('+52', 'Mexico (+52)'),
        ('+691', 'Micronesia (+691)'),
        ('+373', 'Moldova (+373)'),
        ('+377', 'Monaco (+377)'),
        ('+976', 'Mongolia (+976)'),
        ('+382', 'Montenegro (+382)'),
        ('+212', 'Morocco (+212)'),
        ('+258', 'Mozambique (+258)'),
        ('+95', 'Myanmar (+95)'),
        ('+264', 'Namibia (+264)'),
        ('+674', 'Nauru (+674)'),
        ('+977', 'Nepal (+977)'),
        ('+31', 'Netherlands (+31)'),
        ('+64', 'New Zealand (+64)'),
        ('+505', 'Nicaragua (+505)'),
        ('+227', 'Niger (+227)'),
        ('+234', 'Nigeria (+234)'),
        ('+47', 'Norway (+47)'),
        ('+968', 'Oman (+968)'),
        ('+92', 'Pakistan (+92)'),
        ('+680', 'Palau (+680)'),
        ('+507', 'Panama (+507)'),
        ('+675', 'Papua New Guinea (+675)'),
        ('+595', 'Paraguay (+595)'),
        ('+51', 'Peru (+51)'),
        ('+63', 'Philippines (+63)'),
        ('+48', 'Poland (+48)'),
        ('+351', 'Portugal (+351)'),
        ('+974', 'Qatar (+974)'),
        ('+40', 'Romania (+40)'),
        ('+7', 'Russia (+7)'),
        ('+250', 'Rwanda (+250)'),
        ('+966', 'Saudi Arabia (+966)'),
        ('+221', 'Senegal (+221)'),
        ('+381', 'Serbia (+381)'),
        ('+248', 'Seychelles (+248)'),
        ('+232', 'Sierra Leone (+232)'),
        ('+65', 'Singapore (+65)'),
        ('+421', 'Slovakia (+421)'),
        ('+386', 'Slovenia (+386)'),
        ('+677', 'Solomon Islands (+677)'),
        ('+252', 'Somalia (+252)'),
        ('+27', 'South Africa (+27)'),
        ('+82', 'South Korea (+82)'),
        ('+211', 'South Sudan (+211)'),
        ('+34', 'Spain (+34)'),
        ('+94', 'Sri Lanka (+94)'),
        ('+249', 'Sudan (+249)'),
        ('+597', 'Suriname (+597)'),
        ('+268', 'Swaziland (+268)'),
        ('+46', 'Sweden (+46)'),
        ('+41', 'Switzerland (+41)'),
        ('+963', 'Syria (+963)'),
        ('+886', 'Taiwan (+886)'),
        ('+992', 'Tajikistan (+992)'),
        ('+255', 'Tanzania (+255)'),
        ('+66', 'Thailand (+66)'),
        ('+228', 'Togo (+228)'),
        ('+676', 'Tonga (+676)'),
        ('+1868', 'Trinidad and Tobago (+1868)'),
        ('+216', 'Tunisia (+216)'),
        ('+90', 'Turkey (+90)'),
        ('+993', 'Turkmenistan (+993)'),
        ('+688', 'Tuvalu (+688)'),
        ('+256', 'Uganda (+256)'),
        ('+380', 'Ukraine (+380)'),
        ('+971', 'United Arab Emirates (+971)'),
        ('+44', 'United Kingdom (+44)'),
        ('+598', 'Uruguay (+598)'),
        ('+998', 'Uzbekistan (+998)'),
        ('+678', 'Vanuatu (+678)'),
        ('+58', 'Venezuela (+58)'),
        ('+84', 'Vietnam (+84)'),
        ('+967', 'Yemen (+967)'),
        ('+260', 'Zambia (+260)'),
        ('+263', 'Zimbabwe (+263)'),
    ], initial='+1')
    
    # Optional fields for all organization types
    business_type = forms.ChoiceField(
        choices=Organization.BUSINESS_TYPES,
        required=False
    )
    business_registration_number = forms.CharField(
        max_length=50,
        required=False
    )

    class Meta:
        model = Organization
        fields = [
            'name', 'type', 'website', 'industry_tags', 'primary_contact_name', 
            'primary_contact_phone', 'country_code', 'business_type',
            'business_registration_number'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['type'].empty_label = None
        self.fields['primary_contact_name'].required = True
        self.fields['primary_contact_phone'].required = True

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        email = cleaned_data.get('email')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords don't match")
        
        # Validate password strength (same as password reset)
        if password:
            try:
                password_validation.validate_password(password)
            except forms.ValidationError as e:
                raise forms.ValidationError(f"Password: {', '.join(e.messages)}")
        
        # Check if email is already in use
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already registered")
            
        return cleaned_data

    def clean_website(self):
        """Clean and validate website field using centralized validator"""
        website = self.cleaned_data.get('website', '')
        return clean_and_validate_website(website)
    
    def clean_industry_tags(self):
        """Clean and validate industry tags"""
        tags_string = self.cleaned_data.get('industry_tags', '')
        return validate_industry_tags(tags_string)
    
    def clean_business_registration_number(self):
        brn = self.cleaned_data.get('business_registration_number')
        business_type = self.cleaned_data.get('business_type')
        
        if not brn:
            return brn
        
        # For international businesses, just return the value as-is
        if business_type == 'international':
            return brn
        
        # For US businesses, enforce EIN format
        brn_clean = ''.join(e for e in brn if e.isalnum())
        
        # EIN format: XX-XXXXXXX (9 digits)
        if len(brn_clean) != 9 or not brn_clean.isdigit():
            raise forms.ValidationError(
                "EIN must be in the format XX-XXXXXXX (9 digits total)."
            )
        
        # Format as XX-XXXXXXX
        formatted_brn = f"{brn_clean[:2]}-{brn_clean[2:]}"
        return formatted_brn
    
    def clean_primary_contact_phone(self):
        """Validate phone number based on country code"""
        phone = self.cleaned_data.get('primary_contact_phone')
        country_code = self.cleaned_data.get('country_code')
        
        if not phone:
            return phone
        
        # Remove ALL non-digit characters (parentheses, dashes, spaces, etc.)
        phone_digits = ''.join(filter(str.isdigit, phone))
        
        # Validate US and Canada numbers (both use +1)
        if country_code == '+1':
            if len(phone_digits) != 10:
                raise forms.ValidationError("US/Canada phone numbers must be exactly 10 digits")
            # Store just the digits - we'll format on display
            return phone_digits
        
        # For other countries, just ensure it's numeric and reasonable length
        if not phone_digits:
            raise forms.ValidationError("Phone number must contain digits")
        
        if len(phone_digits) < 6:  # Most phone numbers are at least 6 digits
            raise forms.ValidationError("Phone number seems too short")
        
        if len(phone_digits) > 15:  # ITU-T recommendation E.164 max length
            raise forms.ValidationError("Phone number seems too long")
        
        return phone_digits


class EnhancedOrganizationProfileForm(forms.Form):
    """Simplified form that doesn't inherit from ModelForm to avoid model validation"""
    
    name = forms.CharField(
        max_length=50, 
        help_text="Your organization's official name"
    )
    website = forms.CharField(
        max_length=50, 
        required=False,
        help_text="Your main website (without http://)"
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Tell us about your organization, what you do, and what makes you unique...'
        }),
        required=False,
        help_text="Brief description of your organization and what you do"
    )
    logo = forms.ImageField(
        required=False,
        help_text="Recommended size: 400x400 pixels. Supported formats: JPG, PNG, GIF (max 5MB)"
    )
    employee_count = forms.ChoiceField(
        choices=Organization.EMPLOYEE_COUNT_CHOICES,
        required=False,
        help_text="Approximate number of employees"
    )
    founding_year = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'placeholder': f'e.g., {datetime.now().year - 5}',
            'min': '1800',
            'max': str(datetime.now().year)
        }),
        help_text="Year your company was founded"
    )
    headquarters_location = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., San Francisco, CA'
        }),
        help_text="Primary location of your headquarters"
    )
    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'placeholder': 'https://linkedin.com/company/your-company'
        })
    )
    twitter_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'placeholder': 'https://twitter.com/your-company'
        })
    )

    def __init__(self, instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate with existing data
        if instance:
            self.fields['name'].initial = instance.name
            self.fields['website'].initial = instance.website
            self.fields['description'].initial = instance.description
            self.fields['employee_count'].initial = instance.employee_count
            self.fields['founding_year'].initial = instance.founding_year
            self.fields['headquarters_location'].initial = instance.headquarters_location
            self.fields['linkedin_url'].initial = instance.linkedin_url
            self.fields['twitter_url'].initial = instance.twitter_url
        
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            if field_name == 'description':
                field.widget.attrs['class'] = 'form-textarea focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm'
            elif field_name == 'logo':
                field.widget.attrs['class'] = 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'
            elif field_name == 'employee_count':
                # Dropdown styling consistent with registration and filters
                field.widget.attrs.update({
                    'class': 'block w-full px-4 py-3 border-2 border-gray-200 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-sm appearance-none bg-no-repeat bg-right-4 bg-top-1/2',
                    'style': "background-image: url('data:image/svg+xml,%3csvg xmlns=\\'http://www.w3.org/2000/svg\\' fill=\\'none\\' viewBox=\\'0 0 20 20\\'%3e%3cpath stroke=\\'%236b7280\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\' stroke-width=\\'1.5\\' d=\\'M6 8l4 4 4-4\\'/%3e%3c/svg%3e'); background-size: 1.5em 1.5em; background-position: right 0.5rem center;"
                })
            else:
                field.widget.attrs['class'] = 'form-input focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm'

    def clean_website(self):
        """Clean and validate website field using centralized validator"""
        website = self.cleaned_data.get('website', '')
        return clean_and_validate_website(website)

    def clean_founding_year(self):
        """Validate founding year"""
        year = self.cleaned_data.get('founding_year')
        if year:
            current_year = datetime.now().year
            if year < 1800 or year > current_year:
                raise forms.ValidationError(f"Founding year must be between 1800 and {current_year}")
        return year

    def clean_linkedin_url(self):
        """Validate LinkedIn URL"""
        url = self.cleaned_data.get('linkedin_url')
        if url and 'linkedin.com' not in url.lower():
            raise forms.ValidationError("Please enter a valid LinkedIn URL")
        return url

    def clean_twitter_url(self):
        """Validate Twitter URL"""
        url = self.cleaned_data.get('twitter_url')
        if url and not any(domain in url.lower() for domain in ['twitter.com', 'x.com']):
            raise forms.ValidationError("Please enter a valid Twitter/X URL")
        return url
    
    def clean_logo(self):
        """Validate logo file size"""
        logo = self.cleaned_data.get('logo')
        if logo:
            max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)  # Default 10MB
            if logo.size > max_size:
                max_size_mb = max_size / (1024 * 1024)
                raise forms.ValidationError(
                    f"File size must not exceed {max_size_mb:.0f}MB. "
                    f"Your file is {logo.size / (1024 * 1024):.1f}MB."
                )
        return logo

class PartnerPromotionForm(forms.ModelForm):
    """Form for managing partner promotions and exclusive deals"""
    
    class Meta:
        model = PartnerPromotion
        fields = ['title', 'description', 'link_url', 'is_exclusive', 'display_order']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g., "50% Off Enterprise Software Licenses"',
                'maxlength': '100'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Brief description of this exclusive offer or partnership...',
                'maxlength': '500'
            }),
            'link_url': forms.URLInput(attrs={
                'placeholder': 'https://yourcompany.com/fend-exclusive'
            }),
            'display_order': forms.NumberInput(attrs={
                'min': '0',
                'max': '5'
            }),
        }
        help_texts = {
            'title': 'Short, descriptive title for this exclusive offer',
            'description': 'Brief description that will appear on your profile',
            'link_url': 'URL where visitors can learn more or access the offer',
            'is_exclusive': 'Mark if this is an exclusive offer for the Fend network',
            'display_order': 'Lower numbers appear first (0-10)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Update field labels
        self.fields['is_exclusive'].label = 'Exclusive to Fend Network'
        
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            if field_name == 'description':
                field.widget.attrs['class'] = 'form-textarea focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm'
            elif field_name == 'is_exclusive':
                field.widget.attrs['class'] = 'focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded'
            elif field_name == 'display_order':
                # Dropdown styling consistent with registration and filters
                field.widget.attrs.update({
                    'class': 'block w-full px-4 py-3 border-2 border-gray-200 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-sm appearance-none bg-no-repeat bg-right-4 bg-top-1/2',
                    'style': "background-image: url('data:image/svg+xml,%3csvg xmlns=\\'http://www.w3.org/2000/svg\\' fill=\\'none\\' viewBox=\\'0 0 20 20\\'%3e%3cpath stroke=\\'%236b7280\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\' stroke-width=\\'1.5\\' d=\\'M6 8l4 4 4-4\\'/%3e%3c/svg%3e'); background-size: 1.5em 1.5em; background-position: right 0.5rem center;"
                })
            else:
                field.widget.attrs['class'] = 'form-input focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm'


class PilotDefinitionForm(forms.ModelForm):
    """Optional third step for enterprise pilot definition"""
    class Meta:
        model = PilotDefinition
        fields = [
            'description',
            'technical_specs_doc',
            'performance_metrics',
            'compliance_requirements',
            'is_private'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'performance_metrics': forms.Textarea(attrs={'rows': 4}),
            'compliance_requirements': forms.Textarea(attrs={'rows': 4}),
        }


# Keep the original form for backward compatibility
class OrganizationProfileForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'website', 'description', 'logo']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean_logo(self):
        """Validate logo file size"""
        logo = self.cleaned_data.get('logo')
        if logo:
            max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)  # Default 10MB
            if logo.size > max_size:
                max_size_mb = max_size / (1024 * 1024)
                raise forms.ValidationError(
                    f"File size must not exceed {max_size_mb:.0f}MB. "
                    f"Your file is {logo.size / (1024 * 1024):.1f}MB."
                )
        return logo