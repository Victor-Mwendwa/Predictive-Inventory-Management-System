from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions
from core.models import Retailer

User = get_user_model()

class CustomJWTAuthentication:
    """
    Custom JWT authentication that includes user type verification
    """
    
    def authenticate(self, request):
        # Get the token from the request headers
        auth_header = request.headers.get('Authorization', '')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            # Verify the token and get the user
            refresh = RefreshToken(token)
            user_id = refresh.payload.get('user_id')
            user = User.objects.get(pk=user_id)
            
            # Additional verification checks
            if not user.is_active:
                raise AuthenticationFailed(_('User account is disabled'))
            
            # Check if retailer user has an active retailer profile
            if hasattr(user, 'retailer') and not user.retailer.is_active:
                raise AuthenticationFailed(_('Retailer account is inactive'))
            
            return (user, token)
            
        except User.DoesNotExist:
            raise AuthenticationFailed(_('User not found'))
        except Exception as e:
            raise AuthenticationFailed(_('Invalid token'))

class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class IsRetailerUser(permissions.BasePermission):
    """
    Allows access only to retailer users.
    """
    def has_permission(self, request, view):
        return request.user and hasattr(request.user, 'retailer')

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allows access to object owners or admin users.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can do anything
        if request.user and request.user.is_staff:
            return True
            
        # Check if the object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
            
        # Check if the object has a retailer attribute
        if hasattr(obj, 'retailer'):
            return obj.retailer.user == request.user
            
        return False

class HasGroupPermission(permissions.BasePermission):
    """
    Allows access only to users in specific groups.
    """
    def __init__(self, group_names):
        self.group_names = group_names if isinstance(group_names, list) else [group_names]
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        if request.user.is_superuser:
            return True
            
        user_groups = request.user.groups.values_list('name', flat=True)
        return any(group in user_groups for group in self.group_names)

def get_tokens_for_user(user):
    """
    Generate JWT tokens for a user with custom claims
    """
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['user_id'] = user.pk
    refresh['email'] = user.email
    refresh['is_staff'] = user.is_staff
    
    # Add retailer info if applicable
    if hasattr(user, 'retailer'):
        refresh['retailer_id'] = user.retailer.pk
        refresh['retailer_location'] = user.retailer.location
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def create_retailer_user(email, password, **extra_fields):
    """
    Create a new retailer user with profile
    """
    # Check if user already exists
    if User.objects.filter(email=email).exists():
        raise ValueError('User with this email already exists')
    
    # Create user
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        **extra_fields
    )
    
    # Assign to retailer group
    retailer_group = Group.objects.get(name='Retailer')
    user.groups.add(retailer_group)
    
    # Create retailer profile
    retailer = Retailer.objects.create(
        user=user,
        location=extra_fields.get('location', ''),
        contact=extra_fields.get('contact', ''),
        storage_capacity=extra_fields.get('storage_capacity', 0)
    )
    
    return user, retailer

def update_user_password(user, new_password):
    """
    Update user password with validation
    """
    if not new_password or len(new_password) < 8:
        raise ValueError('Password must be at least 8 characters long')
    
    user.set_password(new_password)
    user.save()
    return user

def verify_user_credentials(email, password):
    """
    Verify user credentials and return user if valid
    """
    try:
        user = User.objects.get(email=email)
        if user.check_password(password):
            return user
        return None
    except User.DoesNotExist:
        return None

def deactivate_user_account(user):
    """
    Deactivate a user account and related retailer profile
    """
    user.is_active = False
    user.save()
    
    if hasattr(user, 'retailer'):
        retailer = user.retailer
        retailer.is_active = False
        retailer.save()
    
    return user