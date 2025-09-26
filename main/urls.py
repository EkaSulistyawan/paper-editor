from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('doi_list/', views.doi_list_search, name='doi_list_search'),

    # for paper editor
    path('paper_editor/', views.paper_editor, name='paper_editor'),
    path('paper_summary/', views.paper_summary, name='paper_summary'),
    path('media-context/', views.media_context, name='media_context'),
    path('remove-image/', views.remove_image, name='remove_image'),
    path('save_reference/', views.save_reference, name='save_reference'),
    path('upload_reference/', views.upload_reference, name='upload_reference'),
    path('preview-paragraph/', views.preview_paragraph, name='preview_paragraph'),
]
