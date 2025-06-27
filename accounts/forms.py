from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class SignUpForm(forms.Form):
    full_name = forms.CharField(max_length=150, label='Full Name', widget=forms.TextInput(attrs={
        'placeholder': 'Enter your full name',
        'class': 'form-control',
    }))
    email = forms.EmailField(label='Email Address', widget=forms.EmailInput(attrs={
        'placeholder': 'Enter your email',
        'class': 'form-control',
    }))
    password = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={
        'placeholder': 'Create a password',
        'class': 'form-control',
    }))
    confirm_password = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={
        'placeholder': 'Confirm your password',
        'class': 'form-control',
    }))
    agree_terms = forms.BooleanField(label='I agree to the terms of Service and Privacy Policy', required=True)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Email already exists')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match')
        return cleaned_data

class LoginForm(forms.Form):
    username = forms.CharField(label='Username or Email', widget=forms.TextInput(attrs={
        'placeholder': ' ',
        'class': 'form-control',
        'autocomplete': 'username',
    }))
    password = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={
        'placeholder': ' ',
        'class': 'form-control',
        'autocomplete': 'current-password',
    })) 