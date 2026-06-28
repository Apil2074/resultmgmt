from django.urls import path
from .views_web import exam_list, exam_detail, exam_workflow, exam_edit, exam_delete

urlpatterns = [
    path('', exam_list, name='exam_list'),
    path('<int:pk>/', exam_detail, name='exam_detail'),
    path('<int:pk>/workflow/', exam_workflow, name='exam_workflow'),
    path('<int:pk>/edit/', exam_edit, name='exam_edit'),
    path('<int:pk>/delete/', exam_delete, name='exam_delete'),
]
