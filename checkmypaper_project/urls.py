"""
URL configuration for checkmypaper project.

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
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    
    path('', views.paper_editor, name='paper_editor'),
    path('media-context/', views.media_context, name='media_context'),
    path('remove-image/', views.remove_image, name='remove_image'),
    path('save_reference/', views.save_reference, name='save_reference'),
    path('upload_reference/', views.upload_reference, name='upload_reference'),
    path('home/',views.home,name='home page'),
    path('preview-paragraph/', views.preview_paragraph, name='preview_paragraph'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

