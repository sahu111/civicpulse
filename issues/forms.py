from django import forms

from core.forms import StyledFormMixin

from .models import Issue
from .validators import validate_image


class IssueForm(StyledFormMixin, forms.ModelForm):
    photo = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        help_text="JPEG, PNG or WebP, up to 5 MB.",
    )
    notes = forms.CharField(
        required=False, max_length=500, label="Additional notes",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = Issue
        fields = ("title", "description", "category", "location_text", "latitude", "longitude")
        labels = {"location_text": "Location or landmark"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5, "maxlength": 1000}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001"}),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters.")
        return title

    def clean_description(self):
        text = self.cleaned_data["description"].strip()
        if len(text) < 10:
            raise forms.ValidationError("Description must be at least 10 characters.")
        if len(text) > 1000:
            raise forms.ValidationError("Description can be at most 1000 characters.")
        return text

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        self.photo_mime = validate_image(photo) if photo else ""
        return photo

    def issue_data(self):
        return {k: self.cleaned_data[k] for k in self.Meta.fields}
