"""
URL configuration for Driving_Institute project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('SDIMS_apps.homesandall.urls')),
    path('trainee/', include('SDIMS_apps.trainees.urls')),
    path('courses/', include('SDIMS_apps.courses.urls')),
    path('vehicles/',include('SDIMS_apps.vehicles.urls')),
    path('instructors/', include('SDIMS_apps.instructors.urls')),
    path('training/', include('SDIMS_apps.training.urls')),
    path('mocktest/', include('SDIMS_apps.license_mocktest.urls')),
    path('accounts/', include('SDIMS_apps.accounts.urls')),
    path('accounting/', include('SDIMS_apps.accounting.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)