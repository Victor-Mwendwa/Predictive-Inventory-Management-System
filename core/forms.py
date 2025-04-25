from django import forms
from .models import DemandForecast
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from .models import (
    Product, Inventory, Order, 
    OrderItem, Retailer, ProductCategory
)
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
import re

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'category', 'description',
            'price', 'perishable', 'expiry_days', 'image'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'class': 'form-control'}),
            'expiry_days': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if not re.match(r'^[A-Za-z0-9\-_]+$', sku):
            raise ValidationError(
                "SKU can only contain letters, numbers, hyphens, and underscores."
            )
        return sku

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price <= 0:
            raise ValidationError("Price must be greater than zero.")
        return price

    def clean(self):
        cleaned_data = super().clean()
        perishable = cleaned_data.get('perishable')
        expiry_days = cleaned_data.get('expiry_days')

        if perishable and not expiry_days:
            raise ValidationError({
                'expiry_days': "Expiry days is required for perishable products."
            })

        if not perishable and expiry_days:
            cleaned_data['expiry_days'] = None

        return cleaned_data


class InventoryForm(forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['current_stock', 'safety_stock', 'reorder_point']
        widgets = {
            'current_stock': forms.NumberInput(attrs={
                'min': 0, 
                'class': 'form-control'
            }),
            'safety_stock': forms.NumberInput(attrs={
                'min': 0, 
                'class': 'form-control'
            }),
            'reorder_point': forms.NumberInput(attrs={
                'min': 0, 
                'class': 'form-control'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        safety_stock = cleaned_data.get('safety_stock')
        reorder_point = cleaned_data.get('reorder_point')

        if safety_stock and reorder_point and safety_stock >= reorder_point:
            raise ValidationError(
                "Reorder point must be greater than safety stock level."
            )

        return cleaned_data


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['retailer', 'notes']
        widgets = {
            'retailer': forms.Select(attrs={
                'class': 'form-select',
                'disabled': 'disabled'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Any special instructions...'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and not user.is_staff:
            # For retailer users, set their retailer account as the only option
            if hasattr(user, 'retailer'):
                self.fields['retailer'].queryset = Retailer.objects.filter(pk=user.retailer.pk)
                self.initial['retailer'] = user.retailer
            else:
                self.fields['retailer'].queryset = Retailer.objects.none()
        else:
            # For staff users, show all active retailers
            self.fields['retailer'].queryset = Retailer.objects.filter(is_active=True)
            self.fields['retailer'].widget.attrs.pop('disabled', None)


class OrderItemForm(forms.ModelForm):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(inventory__current_stock__gt=0),
        widget=forms.Select(attrs={
            'class': 'form-select product-select',
            'data-url': '/get-product-details/'
        })
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control quantity-input',
            'min': 1
        })
    )

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity']
        widgets = {
            'unit_price': forms.NumberInput(attrs={
                'readonly': True,
                'class': 'form-control unit-price-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['product'].disabled = True
            self.fields['product'].widget.attrs['class'] = 'form-select disabled'
            self.fields['quantity'].widget.attrs['max'] = self.instance.product.current_stock + self.instance.quantity

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        product = self.cleaned_data.get('product')

        if product and quantity:
            if self.instance.pk:
                # For existing order items, account for previous quantity
                available = product.current_stock + self.instance.quantity
            else:
                available = product.current_stock

            if quantity > available:
                raise ValidationError(
                    f"Only {available} units available in stock."
                )

        return quantity

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk:  # Only for new items
            product = cleaned_data.get('product')
            if product:
                cleaned_data['unit_price'] = product.price
        return cleaned_data


OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class RetailerUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(
        attrs={'class': 'form-control'}
    ))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email


class RetailerForm(forms.ModelForm):
    class Meta:
        model = Retailer
        fields = ['location', 'storage_capacity', 'contact', 'is_active']
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'storage_capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': '0.01'
            }),
            'contact': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_contact(self):
        contact = self.cleaned_data.get('contact')
        if not re.match(r'^\+?[\d\s\-]+$', contact):
            raise ValidationError("Enter a valid phone number.")
        return contact


class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if ProductCategory.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A category with this name already exists.")
        return name


class InventoryAdjustmentForm(forms.Form):
    ADJUSTMENT_TYPES = [
        ('ADD', 'Add Stock'),
        ('REMOVE', 'Remove Stock'),
        ('SET', 'Set Exact Quantity'),
    ]

    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': 'Reason for adjustment...'
        })
    )

    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)

    def clean_quantity(self):
        adjustment_type = self.cleaned_data.get('adjustment_type')
        quantity = self.cleaned_data.get('quantity')

        if adjustment_type == 'REMOVE' and self.product:
            if quantity > self.product.current_stock:
                raise ValidationError(
                    f"Cannot remove more than current stock ({self.product.current_stock})"
                )

        return quantity


class DateRangeForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date cannot be after end date.")
            if (end_date - start_date).days > 365:
                raise ValidationError("Date range cannot exceed 1 year.")

        return cleaned_data


class DemandForecastForm(forms.ModelForm):
    class Meta:
        model = DemandForecast
        fields = ['product', 'forecast_date', 'predicted_demand', 'confidence_score']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'forecast_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'predicted_demand': forms.NumberInput(attrs={
                'min': 0,
                'class': 'form-control'
            }),
            'confidence_score': forms.NumberInput(attrs={
                'min': 0,
                'max': 100,
                'class': 'form-control'
            }),
        }

    def clean_confidence_score(self):
        score = self.cleaned_data.get('confidence_score')
        if not (0 <= score <= 100):
            raise ValidationError("Confidence score must be between 0 and 100.")
        return score