from django.urls import path
from .views_web import (
    exam_list, exam_detail, exam_workflow, exam_edit, exam_delete,
    exam_aggregation_rules, exam_generate_aggregate
)

urlpatterns = [
    path('', exam_list, name='exam_list'),
    path('<int:pk>/', exam_detail, name='exam_detail'),
    path('<int:pk>/workflow/', exam_workflow, name='exam_workflow'),
    path('<int:pk>/edit/', exam_edit, name='exam_edit'),
    path('<int:pk>/delete/', exam_delete, name='exam_delete'),
    path('<int:pk>/aggregate-rules/', exam_aggregation_rules, name='exam_aggregation_rules'),
    path('<int:pk>/generate-aggregate/', exam_generate_aggregate, name='exam_generate_aggregate'),
]
