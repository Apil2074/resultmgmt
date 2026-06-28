from django.urls import path
from .views_web import (
    grade_ledger,
    marksheet,
    marksheet_pdf,
    class_marksheets_pdf,
    ledger_pdf,
    ledger_excel,
    grade_ledger_select,
    marksheet_select,
    public_result_search,
    public_report_card,
)

urlpatterns = [
    # Public Portal
    path('public/', public_result_search, name='public_result_search'),
    path('public/report/<int:exam_id>/<int:student_id>/', public_report_card, name='public_report_card'),
    
    # Authenticated Routes
    path('ledger/', grade_ledger_select, name='grade_ledger_select'),
    path('ledger/<int:exam_id>/<int:class_id>/', grade_ledger, name='grade_ledger'),
    path('marksheet/', marksheet_select, name='marksheet_select'),
    path('marksheet/<int:exam_id>/<int:student_id>/', marksheet, name='marksheet'),
    path('marksheet/<int:exam_id>/<int:student_id>/pdf/', marksheet_pdf, name='marksheet_pdf'),
    path('class-marksheets/<int:exam_id>/<int:class_id>/pdf/', class_marksheets_pdf, name='class_marksheets_pdf'),
    path('ledger/<int:exam_id>/<int:class_id>/pdf/', ledger_pdf, name='ledger_pdf'),
    path('ledger/<int:exam_id>/<int:class_id>/excel/', ledger_excel, name='ledger_excel'),
]
