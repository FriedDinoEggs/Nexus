from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

User = get_user_model()


class CustomUserCreateForm(UserCreationForm):
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get['password']
        confirm_password = cleaned_data.get['confirm_password']

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('會不會輸密碼阿？')

        return cleaned_data


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = '__all__'
