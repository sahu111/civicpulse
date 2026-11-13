from django import forms


class StyledFormMixin:
    """Adds the shared Tailwind input classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                continue
            if isinstance(w, forms.FileInput):
                w.attrs.setdefault("class", "file-input")
            else:
                w.attrs.setdefault("class", "input")
