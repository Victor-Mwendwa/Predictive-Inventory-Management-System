# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from core import views as core_views
from core import views as core_views

urlpatterns = [
    # Admin site
    path('', include('core.urls')),
    path('admin/', admin.site.urls), 
    
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='registration/logout.html'), name='logout'),
    
    # Core application URLs
    path('', core_views.dashboard, name='dashboard'),
    # path('inventory/', include('core.urls')),
    
    # API endpoints
    path('api/', include('api.urls')),
    
    # Reports and analytics
    path('reports/', core_views.reports, name='reports'),
    
    # User profile
    path('profile/', core_views.profile, name='profile'),
    
    path('reports/', core_views.reports, name='reports'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)