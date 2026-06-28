"""
PDF Generators — Marksheet and Grade Ledger using ReportLab
"""
import io
from decimal import Decimal
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
    HRFlowable, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import os

def format_mark(val):
    if val is None:
        return '—'
    from decimal import Decimal
    try:
        dec = Decimal(str(val))
        if dec == dec.to_integral_value():
            return str(int(dec))
        return str(dec.normalize())
    except Exception:
        return str(val)

# Color palette
NAVY = colors.HexColor('#0F172A')
NAVY_LIGHT = colors.HexColor('#1E293B')
GOLD = colors.HexColor('#F59E0B')
EMERALD = colors.HexColor('#10B981')
RED = colors.HexColor('#EF4444')
GRAY = colors.HexColor('#94A3B8')
LIGHT_GRAY = colors.HexColor('#F1F5F9')
WHITE = colors.white
BLACK = colors.black


def _get_logo_image(school, width=3*cm, height=3*cm):
    """Return an Image object for the school logo, or None."""
    try:
        if school.logo and os.path.exists(school.logo.path):
            return Image(school.logo.path, width=width, height=height)
    except Exception:
        pass
    return None


class MarksheetPDFGenerator:
    """Generates a professional individual marksheet PDF matching the Nepalese grade-sheet template."""

    def __init__(self, school, exam, student, result, mark_entries):
        self.school = school
        self.exam = exam
        self.student = student
        self.result = result
        # Sort mark entries by subject order
        self.mark_entries = sorted(list(mark_entries), key=lambda x: x.subject.order if x.subject else 0)
        
        # Enrich subject result remarks
        grade_remarks = {
            'A+': 'Outstanding',
            'A': 'Excellent',
            'B+': 'Very Good',
            'B': 'Good',
            'C+': 'Satisfactory',
            'C': 'Acceptable',
            'D+': 'Basic',
            'D': 'Basic',
            'E': 'Insufficient',
            'NG': 'Not Graded',
        }
        for me in self.mark_entries:
            sr = getattr(me, 'subject_result', None)
            if sr:
                sr.theory_remark = grade_remarks.get(sr.theory_grade, '—') if sr.theory_grade else '—'
                sr.internal_remark = grade_remarks.get(sr.internal_grade, '—') if sr.internal_grade else '—'
                sr.overall_remark = grade_remarks.get(sr.grade, '—') if sr.grade else '—'
                
        # Calculate attendance
        self.present_days = '—'
        self.total_days = '—'
        for me in self.mark_entries:
            if me.present_days is not None:
                self.present_days = me.present_days
            if me.total_days:
                self.total_days = me.total_days
            if self.present_days != '—' and self.total_days != '—':
                break

    def generate(self):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8*cm,
            leftMargin=0.8*cm,
            topMargin=0.8*cm,
            bottomMargin=0.8*cm,
        )
        story = self._build_story()
        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return buffer.getvalue()

    def _header_footer(self, canvas_obj, doc):
        canvas_obj.saveState()
        # Double border around the page in Navy
        navy_color = colors.HexColor('#1E3A8A')
        canvas_obj.setStrokeColor(navy_color)
        canvas_obj.setLineWidth(1)
        canvas_obj.rect(0.6*cm, 0.6*cm, A4[0] - 1.2*cm, A4[1] - 1.2*cm)
        
        # Faint Logo Watermark in the center of the page
        try:
            import os
            if self.school.logo and os.path.exists(self.school.logo.path):
                logo_w = 9*cm
                logo_h = 9*cm
                canvas_obj.setFillAlpha(0.04)
                canvas_obj.setStrokeAlpha(0.04)
                canvas_obj.drawImage(self.school.logo.path, (A4[0]-logo_w)/2, (A4[1]-logo_h)/2, width=logo_w, height=logo_h, mask='auto')
        except Exception:
            pass
        
        # Reset alphas and draw Footer text
        canvas_obj.restoreState()
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.HexColor('#64748b'))
        canvas_obj.drawString(0.9*cm, 0.4*cm, self.school.name)
        canvas_obj.restoreState()

    def _build_story(self):
        styles = getSampleStyleSheet()
        story = []

        # 1. School Header
        logo = _get_logo_image(self.school, 1.6*cm, 1.6*cm)
        align_type = TA_LEFT if logo else TA_CENTER
        
        school_name_style = ParagraphStyle(
            'SchoolName', fontSize=20, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e3a8a'), alignment=TA_CENTER,
            spaceAfter=3, leading=20
        )
        subtitle_style = ParagraphStyle(
            'Subtitle', fontSize=12, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#475569'), alignment=TA_CENTER,
            spaceAfter=3, leading=12
        )
        small_subtitle_style = ParagraphStyle(
            'SmallSubtitle', fontSize=10, fontName='Helvetica',
            textColor=colors.HexColor('#64748b'), alignment=TA_CENTER,
            spaceAfter=2, leading=9.5
        )
        
        school_info = []
        school_info.append(Paragraph(self.school.name, school_name_style))
        school_info.append(Paragraph(self.school.address, subtitle_style))
        
        extra_info_parts = []
        if self.school.phone:
            extra_info_parts.append(f"Phone: {self.school.phone}")
        if self.school.email:
            extra_info_parts.append(f"Email: {self.school.email}")
        if self.school.establishment_year:
            extra_info_parts.append(f"Estd: {self.school.establishment_year}")
            
        if extra_info_parts:
            school_info.append(Paragraph("  |  ".join(extra_info_parts), small_subtitle_style))
            
        if logo:
            header_table = Table([[logo, school_info]], colWidths=[1.8*cm, 17.6*cm], hAlign='CENTER')
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
        else:
            header_table = Table([[school_info]], colWidths=[19.4*cm], hAlign='CENTER')
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            
        story.append(header_table)
        story.append(Spacer(1, 1.5*mm))
        
        # 2. Title Banner
        banner_style = ParagraphStyle(
            'BannerText', fontSize=11, fontName='Helvetica-Bold',
            textColor=colors.white, alignment=TA_CENTER
        )
        banner_table = Table([[Paragraph('GRADE-SHEET', banner_style)]], colWidths=[19.4*cm])
        banner_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(banner_table)
        story.append(Spacer(1, 1.5*mm))
        
        # 3. Student Info Rows (Stacked Tables for perfect alignment and custom widths)
        info_label_style = ParagraphStyle(
            'InfoLabel', fontSize=9, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e3a8a')
        )
        info_value_style = ParagraphStyle(
            'InfoValue', fontSize=9.5, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0f172a')
        )
        
        dob_str = self.student.dob_full or '—'
                
        nested_label_style = ParagraphStyle(
            'NestedLabel', fontSize=9, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e3a8a')
        )
        nested_val_style = ParagraphStyle(
            'NestedVal', fontSize=9.5, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0f172a'), alignment=TA_CENTER
        )
        
        # Row 0 Table: THE GRADE(S) SECURED BY, SYMBOL NO (with spacer column)
        row0_data = [
            [
                Paragraph('THE GRADE(S) SECURED BY :', info_label_style),
                Paragraph(self.student.name.upper(), info_value_style),
                '',
                Paragraph('SYMBOL NO :', info_label_style),
                Paragraph(self.student.symbol_number or '—', info_value_style)
            ]
        ]
        row0_table = Table(row0_data, colWidths=[4.8*cm, 5.2*cm, 2.0*cm, 2.4*cm, 5.0*cm], hAlign='LEFT')
        row0_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LINEBELOW', (1, 0), (1, 0), 1.0, colors.HexColor('#475569')),
            ('LINEBELOW', (4, 0), (4, 0), 1.0, colors.HexColor('#475569')),
        ]))

        # Row 1 Table: REGISTRATION NO, DATE OF BIRTH (with spacer column)
        row1_data = [
            [
                Paragraph('REGISTRATION NO :', info_label_style),
                Paragraph(self.student.registration_number or '—', info_value_style),
                '',
                Paragraph('DATE OF BIRTH :', info_label_style),
                Paragraph(dob_str, info_value_style)
            ]
        ]
        row1_table = Table(row1_data, colWidths=[3.5*cm, 4.5*cm, 4.0*cm, 2.8*cm, 4.6*cm], hAlign='LEFT')
        row1_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LINEBELOW', (1, 0), (1, 0), 1.0, colors.HexColor('#475569')),
            ('LINEBELOW', (4, 0), (4, 0), 1.0, colors.HexColor('#475569')),
        ]))

        # Row 2 Table: CLASS, IN THE, EXAMINATION HELD IN (with spacer column)
        row2_data = [
            [
                Paragraph('CLASS :', info_label_style),
                Paragraph(self.student.class_obj.name if self.student.class_obj else '—', nested_val_style),
                Paragraph('IN THE :', nested_label_style),
                Paragraph(self.exam.name.upper(), nested_val_style),
                '',
                Paragraph('EXAMINATION HELD IN :', info_label_style),
                Paragraph(f"{self.exam.session.name}  B.S.", info_value_style)
            ]
        ]
        row2_table = Table(row2_data, colWidths=[1.5*cm, 1.0*cm, 1.5*cm, 5.5*cm, 2.5*cm, 4.0*cm, 3.4*cm], hAlign='LEFT')
        row2_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LINEBELOW', (1, 0), (1, 0), 1.0, colors.HexColor('#475569')),
            ('LINEBELOW', (3, 0), (3, 0), 1.0, colors.HexColor('#475569')),
            ('LINEBELOW', (6, 0), (6, 0), 1.0, colors.HexColor('#475569')),
        ]))

        # Row 3 Table: ARE GIVEN BELOW.
        row3_data = [[Paragraph('<font color="#64748b">ARE GIVEN BELOW.</font>', info_label_style)]]
        row3_table = Table(row3_data, colWidths=[19.4*cm], hAlign='LEFT')
        row3_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ]))

        story.append(row0_table)
        story.append(Spacer(1, 0.8*mm))
        story.append(row1_table)
        story.append(Spacer(1, 0.8*mm))
        story.append(row2_table)
        story.append(Spacer(1, 0.8*mm))
        story.append(row3_table)
        story.append(Spacer(1, 1.5*mm))
        
        # 4. Grading Table
        th_style = ParagraphStyle(
            'TableHeader', fontSize=7.5, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e3a8a'), alignment=TA_CENTER
        )
        th_left_style = ParagraphStyle(
            'TableHeaderLeft', fontSize=7.5, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e3a8a'), alignment=TA_LEFT
        )
        cell_style = ParagraphStyle(
            'TableCell', fontSize=7.5, fontName='Helvetica', alignment=TA_CENTER
        )
        cell_bold_style = ParagraphStyle(
            'TableCellBold', fontSize=7.5, fontName='Helvetica-Bold', alignment=TA_CENTER
        )
        cell_left_style = ParagraphStyle(
            'TableCellLeft', fontSize=7.5, fontName='Helvetica-Bold', alignment=TA_LEFT
        )
        cell_danger_style = ParagraphStyle(
            'TableCellDanger', fontSize=7.5, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#EF4444')
        )
        cell_fg_style = ParagraphStyle(
            'TableCellFG', fontSize=8.5, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#1d4ed8')
        )
        
        table_headers = [
            Paragraph('Subject Code', th_style),
            Paragraph('Subjects', th_left_style),
            Paragraph('Credit Hour (CH)', th_style),
            Paragraph('Grade Point (GP)', th_style),
            Paragraph('Grade', th_style),
            Paragraph('Final Grade (FG)', th_style),
        ]
        
        table_data = [table_headers]
        span_rules = []
        row_idx = 1
        
        credit_mark_entries = [me for me in self.mark_entries if me.subject.subject_type != 'NON_CREDIT']
        non_credit_mark_entries = [me for me in self.mark_entries if me.subject.subject_type == 'NON_CREDIT']

        for me in credit_mark_entries:
            subj = me.subject
            sr = getattr(me, 'subject_result', None)
            
            if subj.has_practical:
                theory_code = subj.code
                theory_name = f"{subj.name.upper()} TH"
                theory_ch = f"{subj.theory_credit_hour:.2f}"
                
                internal_code = subj.practical_code if subj.practical_code else f"{subj.code}P"
                internal_name = f"{subj.name.upper()} IN"
                internal_ch = f"{subj.practical_credit_hour:.2f}"
                
                if me.special_value:
                    val_display = me.get_special_value_display()
                    row_th = [
                        Paragraph(theory_code, cell_style),
                        Paragraph(theory_name, cell_left_style),
                        Paragraph(theory_ch, cell_style),
                        Paragraph(val_display, cell_danger_style),
                        Paragraph(val_display, cell_danger_style),
                        Paragraph(val_display, cell_danger_style),
                    ]
                    row_in = [
                        Paragraph(internal_code, cell_style),
                        Paragraph(internal_name, cell_left_style),
                        Paragraph(internal_ch, cell_style),
                        Paragraph(val_display, cell_danger_style),
                        Paragraph(val_display, cell_danger_style),
                        "",
                    ]
                else:
                    th_gp = f"{sr.theory_grade_point:.2f}" if sr and sr.theory_grade_point is not None else "0.00"
                    th_g = sr.theory_grade if sr and sr.theory_grade else "NG"
                    th_rem = sr.theory_remark if sr and sr.theory_remark else "—"
                    
                    in_gp = f"{sr.internal_grade_point:.2f}" if sr and sr.internal_grade_point is not None else "0.00"
                    in_g = sr.internal_grade if sr and sr.internal_grade else "NG"
                    in_rem = sr.internal_remark if sr and sr.internal_remark else "—"
                    
                    fg = sr.grade if sr and sr.grade else "NG"
                    
                    row_th = [
                        Paragraph(theory_code, cell_style),
                        Paragraph(theory_name, cell_left_style),
                        Paragraph(theory_ch, cell_style),
                        Paragraph(th_gp, cell_style),
                        Paragraph(th_g, cell_style),
                        Paragraph(fg, cell_fg_style),
                    ]
                    row_in = [
                        Paragraph(internal_code, cell_style),
                        Paragraph(internal_name, cell_left_style),
                        Paragraph(internal_ch, cell_style),
                        Paragraph(in_gp, cell_style),
                        Paragraph(in_g, cell_style),
                        "",
                    ]
                
                table_data.append(row_th)
                table_data.append(row_in)
                span_rules.append(('SPAN', (5, row_idx), (5, row_idx + 1)))
                row_idx += 2
            else:
                code = subj.code
                name = subj.name.upper()
                ch = f"{subj.theory_credit_hour:.2f}"
                
                if me.special_value:
                    val_display = me.get_special_value_display()
                    row = [
                        Paragraph(code, cell_style),
                        Paragraph(name, cell_left_style),
                        Paragraph(ch, cell_style),
                        Paragraph(val_display, cell_danger_style),
                        Paragraph(val_display, cell_danger_style),
                        Paragraph(val_display, cell_danger_style),
                    ]
                else:
                    gp = f"{sr.grade_point:.2f}" if sr and sr.grade_point is not None else "0.00"
                    g = sr.grade if sr and sr.grade else "NG"
                    rem = sr.overall_remark if sr and sr.overall_remark else "—"
                    
                    row = [
                        Paragraph(code, cell_style),
                        Paragraph(name, cell_left_style),
                        Paragraph(ch, cell_style),
                        Paragraph(gp, cell_style),
                        Paragraph(g, cell_style),
                        Paragraph(g, cell_fg_style),
                    ]
                
                table_data.append(row)
                row_idx += 1
                
        if len(table_data) == 1:
            table_data.append([
                Paragraph('No marks recorded.', cell_style),
                '', '', '', '', ''
            ])
            span_rules.append(('SPAN', (0, row_idx), (5, row_idx)))
            row_idx += 1
            
        if self.result:
            footer_label_style = ParagraphStyle(
                'FooterLabel', fontName='Helvetica-Bold', fontSize=8.5,
                textColor=colors.HexColor('#1e3a8a'), alignment=TA_RIGHT
            )
            gpa_val = f"{self.result.overall_gpa:.2f}" if self.result.overall_gpa is not None else "0.00"
            rank_val = str(self.result.class_rank) if self.result.class_rank is not None else "—"
            
            row_gpa = [
                Paragraph('Grade Point Average (GPA)', footer_label_style),
                '', '', '',
                Paragraph(gpa_val, cell_fg_style),
                ''
            ]
            row_rank = [
                Paragraph('Rank in Class', footer_label_style),
                '', '', '',
                Paragraph(rank_val, cell_bold_style),
                ''
            ]
            
            table_data.append(row_gpa)
            table_data.append(row_rank)
            
            span_rules.append(('SPAN', (0, row_idx), (3, row_idx)))
            span_rules.append(('SPAN', (0, row_idx + 1), (3, row_idx + 1)))
            row_idx += 2

        if non_credit_mark_entries:
            th_non_credit_style = ParagraphStyle(
                'ThNonCredit', fontName='Helvetica-Bold', fontSize=8.5,
                textColor=colors.HexColor('#1e3a8a'), alignment=TA_LEFT
            )
            row_header = [
                Paragraph('Non-Credit Subjects', th_non_credit_style),
                '', '', '', '', ''
            ]
            table_data.append(row_header)
            span_rules.append(('SPAN', (0, row_idx), (5, row_idx)))
            row_idx += 1
            
            for me in non_credit_mark_entries:
                subj = me.subject
                sr = getattr(me, 'subject_result', None)
                
                if subj.has_practical:
                    theory_code = subj.code
                    theory_name = f"{subj.name.upper()} TH"
                    theory_ch = f"{subj.theory_credit_hour:.2f}"
                    
                    internal_code = subj.practical_code if subj.practical_code else f"{subj.code}P"
                    internal_name = f"{subj.name.upper()} IN"
                    internal_ch = f"{subj.practical_credit_hour:.2f}"
                    
                    if me.special_value:
                        val_display = me.get_special_value_display()
                        row_th = [
                            Paragraph(theory_code, cell_style),
                            Paragraph(theory_name, cell_left_style),
                            Paragraph(theory_ch, cell_style),
                            Paragraph(val_display, cell_danger_style),
                            Paragraph(val_display, cell_danger_style),
                            Paragraph(val_display, cell_danger_style),
                        ]
                        row_in = [
                            Paragraph(internal_code, cell_style),
                            Paragraph(internal_name, cell_left_style),
                            Paragraph(internal_ch, cell_style),
                            Paragraph(val_display, cell_danger_style),
                            Paragraph(val_display, cell_danger_style),
                            "",
                        ]
                    else:
                        th_gp = f"{sr.theory_grade_point:.2f}" if sr and sr.theory_grade_point is not None else "0.00"
                        th_g = sr.theory_grade if sr and sr.theory_grade else "NG"
                        th_rem = sr.theory_remark if sr and sr.theory_remark else "—"
                        
                        in_gp = f"{sr.internal_grade_point:.2f}" if sr and sr.internal_grade_point is not None else "0.00"
                        in_g = sr.internal_grade if sr and sr.internal_grade else "NG"
                        in_rem = sr.internal_remark if sr and sr.internal_remark else "—"
                        
                        fg = sr.grade if sr and sr.grade else "NG"
                        
                        row_th = [
                            Paragraph(theory_code, cell_style),
                            Paragraph(theory_name, cell_left_style),
                            Paragraph(theory_ch, cell_style),
                            Paragraph(th_gp, cell_style),
                            Paragraph(th_g, cell_style),
                            Paragraph(fg, cell_fg_style),
                        ]
                        row_in = [
                            Paragraph(internal_code, cell_style),
                            Paragraph(internal_name, cell_left_style),
                            Paragraph(internal_ch, cell_style),
                            Paragraph(in_gp, cell_style),
                            Paragraph(in_g, cell_style),
                            "",
                        ]
                    
                    table_data.append(row_th)
                    table_data.append(row_in)
                    span_rules.append(('SPAN', (5, row_idx), (5, row_idx + 1)))
                    row_idx += 2
                else:
                    code = subj.code
                    name = subj.name.upper()
                    ch = f"{subj.theory_credit_hour:.2f}"
                    
                    if me.special_value:
                        val_display = me.get_special_value_display()
                        row = [
                            Paragraph(code, cell_style),
                            Paragraph(name, cell_left_style),
                            Paragraph(ch, cell_style),
                            Paragraph(val_display, cell_danger_style),
                            Paragraph(val_display, cell_danger_style),
                            Paragraph(val_display, cell_danger_style),
                        ]
                    else:
                        gp = f"{sr.grade_point:.2f}" if sr and sr.grade_point is not None else "0.00"
                        g = sr.grade if sr and sr.grade else "NG"
                        rem = sr.overall_remark if sr and sr.overall_remark else "—"
                        
                        row = [
                            Paragraph(code, cell_style),
                            Paragraph(name, cell_left_style),
                            Paragraph(ch, cell_style),
                            Paragraph(gp, cell_style),
                            Paragraph(g, cell_style),
                            Paragraph(g, cell_fg_style),
                        ]
                    
                    table_data.append(row)
                    row_idx += 1
            
        col_widths = [3.0*cm, 5.5*cm, 2.2*cm, 2.2*cm, 2.0*cm, 2.4*cm]
        marks_table = Table(table_data, colWidths=col_widths)
        
        table_style_commands = [
            ('GRID', (0, 0), (-1, -1), 1.2, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (5, 1), (5, -1), colors.HexColor('#f8fafc')),
        ]
        for rule in span_rules:
            table_style_commands.append(rule)
            
        marks_table.setStyle(TableStyle(table_style_commands))
        story.append(marks_table)
        story.append(Spacer(1, 3*mm))
        
        # 5. Bottom Meta & Legend Block
        note_title_style = ParagraphStyle(
            'NoteTitle', fontSize=7.0, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e293b'), spaceAfter=1
        )
        note_text_style = ParagraphStyle(
            'NoteText', fontSize=6.0, fontName='Helvetica',
            textColor=colors.HexColor('#475569'), leading=8
        )
        
        note_flowables = [
            Paragraph('NOTE :', note_title_style),
            Paragraph('&bull; One credit hour equals 32 working hours.', note_text_style),
            Paragraph('&bull; Internal (In): This covers the participation, practical/project works, community works, internship, presentations and terminal examinations.', note_text_style),
            Paragraph('&bull; Theory (Th): This covers written external examination.', note_text_style),
        ]
        
        note_box = Table([[note_flowables]], colWidths=[10.8*cm])
        note_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafb')),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#e2e8f0')),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        legend_th_style = ParagraphStyle(
            'LegendTh', fontSize=6.5, fontName='Helvetica-Bold',
            textColor=colors.black, alignment=TA_CENTER
        )
        legend_td_style = ParagraphStyle(
            'LegendTd', fontSize=6.5, fontName='Helvetica',
            textColor=colors.black, alignment=TA_CENTER
        )
        legend_td_bold_style = ParagraphStyle(
            'LegendTdBold', fontSize=6.5, fontName='Helvetica-Bold',
            textColor=colors.black, alignment=TA_CENTER
        )
        
        legend_headers = [
            Paragraph('Grade Point', legend_th_style),
            Paragraph('Grade', legend_th_style),
            Paragraph('Interval', legend_th_style),
            Paragraph('Description', legend_th_style),
        ]
        
        legend_rows = [
            [Paragraph('4.0', legend_td_style), Paragraph('A+', legend_td_bold_style), Paragraph('90 To 100', legend_td_style), Paragraph('Outstanding', legend_td_style)],
            [Paragraph('3.6', legend_td_style), Paragraph('A', legend_td_bold_style), Paragraph('80 To Below 90', legend_td_style), Paragraph('Excellent', legend_td_style)],
            [Paragraph('3.2', legend_td_style), Paragraph('B+', legend_td_bold_style), Paragraph('70 To Below 80', legend_td_style), Paragraph('Very Good', legend_td_style)],
            [Paragraph('2.8', legend_td_style), Paragraph('B', legend_td_bold_style), Paragraph('60 To Below 70', legend_td_style), Paragraph('Good', legend_td_style)],
            [Paragraph('2.4', legend_td_style), Paragraph('C+', legend_td_bold_style), Paragraph('50 To Below 60', legend_td_style), Paragraph('Satisfactory', legend_td_style)],
            [Paragraph('2.0', legend_td_style), Paragraph('C', legend_td_bold_style), Paragraph('40 To Below 50', legend_td_style), Paragraph('Acceptable', legend_td_style)],
            [Paragraph('1.6', legend_td_style), Paragraph('D', legend_td_bold_style), Paragraph('35 To Below 40', legend_td_style), Paragraph('Basic', legend_td_style)],
            [Paragraph('0.0', legend_td_style), Paragraph('NG', legend_td_bold_style), Paragraph('0 To Below 35', legend_td_style), Paragraph('Not Graded', legend_td_style)],
        ]
        
        legend_table_data = [legend_headers] + legend_rows
        legend_table = Table(legend_table_data, colWidths=[1.6*cm, 1.3*cm, 2.7*cm, 2.6*cm])
        legend_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        att_label_style = ParagraphStyle(
            'AttLabel', fontSize=8, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e293b')
        )
        att_val_style = ParagraphStyle(
            'AttVal', fontSize=8, fontName='Helvetica-Bold',
            textColor=colors.black, alignment=TA_CENTER
        )
        
        att_table_data = [
            [
                Paragraph('ATTENDANCE :', att_label_style),
                Paragraph(str(self.present_days), att_val_style),
                Paragraph('OUT OF', att_label_style),
                Paragraph(str(self.total_days), att_val_style),
                Paragraph('DAYS', att_label_style)
            ]
        ]
        att_table = Table(att_table_data, colWidths=[2.3*cm, 1.2*cm, 1.3*cm, 1.2*cm, 1.1*cm])
        att_table.setStyle(TableStyle([
            ('LINEBELOW', (1, 0), (1, 0), 0.75, colors.black),
            ('LINEBELOW', (3, 0), (3, 0), 0.75, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        
        import datetime
        current_date_str = datetime.date.today().strftime('%Y-%m-%d')
        
        issue_table_data = [
            [
                Paragraph('DATE OF ISSUE :', att_label_style),
                Paragraph(current_date_str, att_val_style)
            ]
        ]
        issue_table = Table(issue_table_data, colWidths=[2.5*cm, 2.5*cm])
        issue_table.setStyle(TableStyle([
            ('LINEBELOW', (1, 0), (1, 0), 0.75, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        
        left_flowables = [
            att_table,
            Spacer(1, 2*mm),
            issue_table,
            Spacer(1, 3*mm),
            note_box
        ]
        
        bottom_sections_table = Table([[left_flowables, legend_table]], colWidths=[11.2*cm, 8.2*cm])
        bottom_sections_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(bottom_sections_table)
        story.append(Spacer(1, 0.6*cm))
        
        # 6. Signatures
        sig_label_style = ParagraphStyle(
            'SigLabel', fontSize=8, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e293b'), alignment=TA_CENTER
        )
        sig_table_data = [
            [
                Paragraph('CLASS TEACHER', sig_label_style),
                '',
                Paragraph('CHECKED BY', sig_label_style),
                '',
                Paragraph('HEAD TEACHER', sig_label_style)
            ]
        ]
        sig_table = Table(sig_table_data, colWidths=[4.4*cm, 3.1*cm, 4.4*cm, 3.1*cm, 4.4*cm])
        sig_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (0, 0), 0.75, colors.black),
            ('LINEABOVE', (2, 0), (2, 0), 0.75, colors.black),
            ('LINEABOVE', (4, 0), (4, 0), 0.75, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(sig_table)
        
        return story


class LedgerPDFGenerator:
    """Generates a landscape grade ledger PDF matching the standard 4-row Nepalese layout."""

    def __init__(self, school, exam, cls, subjects, student_results, mark_map):
        self.school = school
        self.exam = exam
        self.cls = cls
        self.subjects = sorted(list(subjects), key=lambda x: x.order)
        self.student_results = list(student_results)
        self.mark_map = mark_map

    def generate(self):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=0.8*cm,
            leftMargin=0.8*cm,
            topMargin=1.0*cm,
            bottomMargin=1.0*cm,
        )
        story = self._build_story()
        doc.build(story)
        return buffer.getvalue()

    def _build_story(self):
        styles = getSampleStyleSheet()
        story = []
        
        # Header style with small fonts to fit standard ledger columns
        h_style = ParagraphStyle(
            'H', fontSize=5.5, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1e3a8a'), alignment=TA_CENTER
        )
        h_sub_style = ParagraphStyle(
            'HSub', fontSize=5, fontName='Helvetica-Bold',
            textColor=colors.black, alignment=TA_CENTER
        )
        c_style = ParagraphStyle(
            'C', fontSize=5.5, fontName='Helvetica', alignment=TA_CENTER
        )
        name_style = ParagraphStyle(
            'N', fontSize=5.5, fontName='Helvetica-Bold', alignment=TA_LEFT
        )

        # Dynamic partitioning of subjects to fit A4 Landscape width (28.1 cm printable area)
        PRINTABLE_WIDTH = 28.1 * cm
        LEFT_WIDTH = 7.8 * cm
        RIGHT_WIDTH = 6.2 * cm
        
        pages = []
        current_page_subjects = []
        current_width = LEFT_WIDTH
        
        for subj in self.subjects:
            try:
                ms = subj.marking_structure
                has_int = ms.has_internal
            except Exception:
                has_int = False
            subj_width = (6 if has_int else 4) * 0.85 * cm
            
            if current_width + subj_width > PRINTABLE_WIDTH:
                pages.append((current_page_subjects, False))
                current_page_subjects = [subj]
                current_width = LEFT_WIDTH + subj_width
            else:
                current_page_subjects.append(subj)
                current_width += subj_width
                
        if current_page_subjects:
            if current_width + RIGHT_WIDTH <= PRINTABLE_WIDTH:
                pages.append((current_page_subjects, True))
            else:
                if len(current_page_subjects) > 1:
                    popped = current_page_subjects.pop()
                    pages.append((current_page_subjects, False))
                    pages.append(([popped], True))
                else:
                    pages.append((current_page_subjects, False))
                    pages.append(([], True))
                    
        if not pages:
            pages.append(([], True))

        from reportlab.platypus import PageBreak

        for page_idx, (page_subjs, include_summary) in enumerate(pages):
            # Title on each horizontal section page
            title_style = ParagraphStyle('T', fontSize=12, fontName='Helvetica-Bold',
                                          textColor=colors.HexColor('#0F172A'), alignment=TA_CENTER)
            sub_style = ParagraphStyle('S', fontSize=8, fontName='Helvetica',
                                       textColor=colors.HexColor('#475569'), alignment=TA_CENTER)
            story.append(Paragraph(self.school.name, title_style))
            story.append(Paragraph(
                f'GRADE LEDGER — {self.exam.name} | {self.cls.full_name} | {self.exam.session.name} (Part {page_idx + 1} of {len(pages)})',
                sub_style
            ))
            story.append(Spacer(1, 3*mm))

            # Build 4-row header arrays
            header1 = [
                Paragraph('SN', h_style),
                Paragraph('Symbol No', h_style),
                Paragraph('REG NO', h_style),
                Paragraph('Student Name', h_style),
                Paragraph('Date of Birth', h_style),
            ]
            header2 = ['', '', '', '', Paragraph('Credit Hour', h_sub_style)]
            header3 = ['', '', '', '', Paragraph('Full Marks', h_sub_style)]
            header4 = ['', '', '', '', Paragraph('DOB', h_sub_style)]
            
            col_idx = 5
            span_rules = []
            
            # Student info columns span 4 rows vertically
            span_rules.append(('SPAN', (0, 0), (0, 3))) # SN
            span_rules.append(('SPAN', (1, 0), (1, 3))) # Symbol No
            span_rules.append(('SPAN', (2, 0), (2, 3))) # REG NO
            span_rules.append(('SPAN', (3, 0), (3, 3))) # Student Name

            for subj in page_subjs:
                try:
                    ms = subj.marking_structure
                    has_int = ms.has_internal
                except Exception:
                    has_int = False
                    ms = None
                    
                n_cols = 6 if has_int else 4
                
                # Row 0: Subject Name
                header1.append(Paragraph(subj.name.upper(), h_style))
                for _ in range(n_cols - 1):
                    header1.append('')
                span_rules.append(('SPAN', (col_idx, 0), (col_idx + n_cols - 1, 0)))
                
                # Row 1: Credit Hour values
                th_ch = f"{subj.theory_credit_hour:.2f}"
                pr_ch = f"{subj.practical_credit_hour:.2f}" if has_int else ""
                header2.append(Paragraph(th_ch, h_sub_style))
                if has_int:
                    header2.append(Paragraph(pr_ch, h_sub_style))
                    for _ in range(4):
                        header2.append('')
                    span_rules.append(('SPAN', (col_idx + 2, 1), (col_idx + 5, 1)))
                else:
                    for _ in range(3):
                        header2.append('')
                    span_rules.append(('SPAN', (col_idx + 1, 1), (col_idx + 3, 1)))
                    
                # Row 2: Full Marks values
                th_fm = str(ms.theory_full_marks) if ms else "100"
                pr_fm = str(ms.internal_full_marks) if has_int and ms else ""
                header3.append(Paragraph(th_fm, h_sub_style))
                if has_int:
                    header3.append(Paragraph(pr_fm, h_sub_style))
                    for _ in range(4):
                        header3.append('')
                    span_rules.append(('SPAN', (col_idx + 2, 2), (col_idx + 5, 2)))
                else:
                    for _ in range(3):
                        header3.append('')
                    span_rules.append(('SPAN', (col_idx + 1, 2), (col_idx + 3, 2)))
                    
                # Row 3: Component headers
                if has_int:
                    header4.append(Paragraph('Th', h_sub_style))
                    header4.append(Paragraph('In', h_sub_style))
                    header4.append(Paragraph('Th GP', h_sub_style))
                    header4.append(Paragraph('In GP', h_sub_style))
                    header4.append(Paragraph('AVG GPA', h_sub_style))
                    header4.append(Paragraph('Grade', h_sub_style))
                else:
                    header4.append(Paragraph('Th', h_sub_style))
                    header4.append(Paragraph('Th GP', h_sub_style))
                    header4.append(Paragraph('AVG GPA', h_sub_style))
                    header4.append(Paragraph('Grade', h_sub_style))
                    
                col_idx += n_cols

            # Summary columns
            if include_summary:
                sum_cols = ['Total Credit Hour', 'GPA', 'Grade', 'Rank', 'Attendance', 'Result']
                for col_name in sum_cols:
                    header1.append(Paragraph(col_name, h_style))
                    header2.append('')
                    header3.append('')
                    header4.append('')
                    
                    # Span vertically 4 rows
                    span_rules.append(('SPAN', (col_idx, 0), (col_idx, 3)))
                    col_idx += 1

            # Calculate exact column widths for this page to fill standard A4 landscape width exactly
            total_weights = 0.0
            for s in page_subjs:
                try:
                    ms = s.marking_structure
                    has_int = ms.has_internal
                except Exception:
                    has_int = False
                if has_int:
                    total_weights += 5.8  # weights: Th(1.0), In(1.0), Th GP(1.0), In GP(1.0), AVG GPA(1.1), Grade(0.7)
                else:
                    total_weights += 3.8  # weights: Th(1.0), Th GP(1.0), AVG GPA(1.1), Grade(0.7)

            current_right_width = RIGHT_WIDTH if include_summary else 0.0 * cm
            printable_width = 28.1 * cm
            remaining_width = printable_width - LEFT_WIDTH - current_right_width
            unit_width = remaining_width / total_weights if total_weights > 0 else 0.85 * cm
            
            col_widths = [0.5*cm, 1.2*cm, 2.0*cm, 3.0*cm, 1.1*cm] # Left columns (sum to 7.8 cm)
            for s in page_subjs:
                try:
                    ms = s.marking_structure
                    has_int = ms.has_internal
                except Exception:
                    has_int = False
                if has_int:
                    col_widths += [
                        1.0 * unit_width,  # Th
                        1.0 * unit_width,  # In
                        1.0 * unit_width,  # Th GP
                        1.0 * unit_width,  # In GP
                        1.1 * unit_width,  # AVG GPA
                        0.7 * unit_width   # Grade
                    ]
                else:
                    col_widths += [
                        1.0 * unit_width,  # Th
                        1.0 * unit_width,  # Th GP
                        1.1 * unit_width,  # AVG GPA
                        0.7 * unit_width   # Grade
                    ]
            if include_summary:
                col_widths += [1.4*cm, 0.9*cm, 0.9*cm, 0.8*cm, 1.2*cm, 1.0*cm] # Summary columns (sum to 6.2 cm)

            # Populate student rows
            data_rows = []
            for sn, sr in enumerate(self.student_results, 1):
                student = sr.student
                dob_str = student.dob_bs or '—'
                
                row = [
                    Paragraph(str(sn), c_style),
                    Paragraph(student.symbol_number or '—', c_style),
                    Paragraph(student.registration_number or '—', c_style),
                    Paragraph(student.name, name_style),
                    Paragraph(dob_str, c_style),
                ]
                
                for subj in page_subjs:
                    try:
                        ms = subj.marking_structure
                        has_int = ms.has_internal
                    except Exception:
                        has_int = False
                        
                    me = self.mark_map.get((student.id, subj.id))
                    sr_sub = getattr(me, 'subject_result', None) if me else None
                    
                    if me:
                        if me.special_value:
                            val = me.get_special_value_display()
                            row.append(Paragraph(val, c_style))
                            if has_int:
                                row.append(Paragraph(val, c_style))
                                row.append(Paragraph(val, c_style))
                                row.append(Paragraph(val, c_style))
                            else:
                                row.append(Paragraph(val, c_style))
                            row.append(Paragraph(val, c_style))
                            row.append(Paragraph(val, c_style))
                        else:
                            th_ob = format_mark(me.theory_obtained)
                            row.append(Paragraph(th_ob, c_style))
                            
                            if has_int:
                                in_ob = format_mark(me.internal_obtained)
                                row.append(Paragraph(in_ob, c_style))
                                
                            th_gp = f"{sr_sub.theory_grade_point:.2f}" if sr_sub and sr_sub.theory_grade_point is not None else '0.00'
                            row.append(Paragraph(th_gp, c_style))
                            
                            if has_int:
                                in_gp = f"{sr_sub.internal_grade_point:.2f}" if sr_sub and sr_sub.internal_grade_point is not None else '0.00'
                                row.append(Paragraph(in_gp, c_style))
                                
                            gpa = f"{sr_sub.grade_point:.2f}" if sr_sub and sr_sub.grade_point is not None else '0.00'
                            row.append(Paragraph(gpa, c_style))
                            
                            grade = sr_sub.grade if sr_sub and sr_sub.grade else 'NG'
                            row.append(Paragraph(grade, c_style))
                    else:
                        row.append(Paragraph('—', c_style))
                        if has_int:
                            row.append(Paragraph('—', c_style))
                            row.append(Paragraph('—', c_style))
                            row.append(Paragraph('—', c_style))
                        else:
                            row.append(Paragraph('—', c_style))
                        row.append(Paragraph('—', c_style))
                        row.append(Paragraph('—', c_style))

                if include_summary:
                    att = '—'
                    total_present = 0
                    total_days = 0
                    has_attendance = False
                    for s in self.subjects:
                        m_entry = self.mark_map.get((student.id, s.id))
                        if m_entry:
                            if m_entry.present_days is not None:
                                total_present += m_entry.present_days
                                has_attendance = True
                            if m_entry.total_days:
                                total_days += m_entry.total_days
                    if has_attendance and total_days > 0:
                        att = f"{round((total_present / total_days) * 100, 1)}%"
                        
                    row += [
                        Paragraph(str(sr.total_credit_hours), c_style),
                        Paragraph(str(sr.overall_gpa or '—'), c_style),
                        Paragraph(sr.final_grade or '—', c_style),
                        Paragraph(str(sr.class_rank or '—'), c_style),
                        Paragraph(att, c_style),
                        Paragraph('P' if sr.is_pass else 'F', c_style),
                    ]
                data_rows.append(row)

            all_data = [header1, header2, header3, header4] + data_rows
            table = Table(all_data, colWidths=col_widths, repeatRows=4)
            
            # Build TableStyle
            t_styles = [
                ('GRID', (0, 0), (-1, -1), 1.0, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('BACKGROUND', (0, 0), (-1, 3), colors.HexColor('#f8fafc')),
                ('ROWBACKGROUNDS', (0, 4), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ]
            
            # Color subject headers
            for idx in range(5, col_idx - (6 if include_summary else 0)):
                t_styles.append(('BACKGROUND', (idx, 0), (idx, 0), colors.HexColor('#e2e8f0')))
                
            # Color AVG GPA and Grade columns
            col_c = 5
            for subj in page_subjs:
                try:
                    ms = subj.marking_structure
                    has_int = ms.has_internal
                except Exception:
                    has_int = False
                
                n = 6 if has_int else 4
                avg_gpa_idx = col_c + (4 if has_int else 2)
                grade_idx = col_c + (5 if has_int else 3)
                t_styles.append(('BACKGROUND', (avg_gpa_idx, 4), (avg_gpa_idx, -1), colors.HexColor('#f8fafc')))
                t_styles.append(('BACKGROUND', (grade_idx, 4), (grade_idx, -1), colors.HexColor('#f8fafc')))
                col_c += n
                
            for rule in span_rules:
                t_styles.append(rule)
                
            table.setStyle(TableStyle(t_styles))
            story.append(table)
            
            if page_idx < len(pages) - 1:
                story.append(PageBreak())
        return story


class ClassMarksheetsPDFGenerator:
    """Generates a merged PDF of all student marksheets in a class."""

    def __init__(self, school, exam, cls, student_results, student_mark_map):
        self.school = school
        self.exam = exam
        self.cls = cls
        self.student_results = student_results
        self.student_mark_map = student_mark_map

    def generate(self):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8*cm,
            leftMargin=0.8*cm,
            topMargin=0.8*cm,
            bottomMargin=0.8*cm,
        )
        
        story = []
        from reportlab.platypus import PageBreak
        
        for idx, sr in enumerate(self.student_results):
            student = sr.student
            mark_entries = self.student_mark_map.get(student.id, [])
            
            student_generator = MarksheetPDFGenerator(self.school, self.exam, student, sr, mark_entries)
            student_story = student_generator._build_story()
            
            story.extend(student_story)
            if idx < len(self.student_results) - 1:
                story.append(PageBreak())
                
        # Re-use the header/footer drawing method of MarksheetPDFGenerator from the first student's generator
        if self.student_results:
            first_sr = self.student_results[0]
            first_student = first_sr.student
            first_mark_entries = self.student_mark_map.get(first_student.id, [])
            dummy_generator = MarksheetPDFGenerator(self.school, self.exam, first_student, first_sr, first_mark_entries)
            doc.build(story, onFirstPage=dummy_generator._header_footer, onLaterPages=dummy_generator._header_footer)
        else:
            doc.build(story)
            
        return buffer.getvalue()




class NEB11MarksheetPDFGenerator(MarksheetPDFGenerator):
    """Generates an NEB Grade 11 format marksheet."""
    
    def get_story(self):
        story = []
        
        # 1. School Header
        school_name_style = ParagraphStyle(
            'SchoolNameNEB', fontSize=22, fontName='Times-Bold',
            alignment=TA_CENTER, textColor=colors.black,
            leading=26, spaceAfter=4
        )
        address_style = ParagraphStyle(
            'AddressNEB', fontSize=12, fontName='Times-Roman',
            alignment=TA_CENTER, textColor=colors.black,
            leading=16, spaceAfter=4
        )
        see_style = ParagraphStyle(
            'SEENEB', fontSize=14, fontName='Times-Bold',
            alignment=TA_CENTER, textColor=colors.black, spaceBefore=4, spaceAfter=4,
            leading=18
        )
        gs_style = ParagraphStyle(
            'GSNEB', fontSize=16, fontName='Times-Bold',
            alignment=TA_CENTER, textColor=colors.HexColor('#1e3a8a'),
            leading=20
        )
        
        school_info = [
            Paragraph(self.school.name, school_name_style),
            Paragraph(self.school.address, address_style),
        ]
        if self.school.establishment_year:
            school_info.append(Paragraph(f"Estd: {self.school.establishment_year}", address_style))
        school_info.extend([
            Paragraph("SECONDARY EDUCATION EXAMINATION", see_style),
            Paragraph("<u>GRADE-SHEET</u>", gs_style)
        ])
        
        logo = _get_logo_image(self.school, width=2.5*cm, height=2.5*cm)
        if logo:
            header_table = Table([[logo, school_info, ""]], colWidths=[2.5*cm, 14.4*cm, 2.5*cm], hAlign='CENTER')
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
        else:
            header_table = Table([[school_info]], colWidths=[19.4*cm], hAlign='CENTER')
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            
        story.append(header_table)
        story.append(Spacer(1, 2*mm))
        
        # 2. Student Info
        info_label_style = ParagraphStyle(
            'InfoLabelNEB', fontSize=9, fontName='Times-Bold',
            textColor=colors.HexColor('#1e3a8a'), leading=12
        )
        info_value_style = ParagraphStyle(
            'InfoValueNEB', fontSize=9, fontName='Times-Bold',
            textColor=colors.black, leading=12
        )
        
        ts_info = TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])

        dob_str = getattr(self.student, 'dob_full', '—') or '—'
        reg_no = self.student.registration_number or "—"
        sym_no = self.student.symbol_number or "—"
        session_name = self.exam.session.name if self.exam and self.exam.session else "—"

        row1 = Table([
            [
                Paragraph('THE&nbsp;GRADE(S)&nbsp;SECURED&nbsp;BY:', info_label_style), Paragraph(self.student.name.upper(), info_value_style),
                Paragraph('DATE&nbsp;OF&nbsp;BIRTH:', info_label_style), Paragraph(dob_str, info_value_style)
            ]
        ], colWidths=[4.6*cm, 6.0*cm, 3.0*cm, 5.8*cm], hAlign='LEFT')
        row1.setStyle(ts_info)
        
        row2 = Table([
            [
                Paragraph('REGISTRATION&nbsp;NO.:', info_label_style), Paragraph(reg_no, info_value_style),
                Paragraph('SYMBOL&nbsp;NO.:', info_label_style), Paragraph(sym_no, info_value_style),
                Paragraph('GRADE:', info_label_style), Paragraph('(11) ELEVEN', info_value_style)
            ]
        ], colWidths=[3.6*cm, 2.7*cm, 2.4*cm, 2.0*cm, 1.5*cm, 7.2*cm], hAlign='LEFT')
        row2.setStyle(ts_info)
        
        row3 = Table([
            [
                Paragraph('IN&nbsp;THE&nbsp;EXAMINATION&nbsp;CONDUCTED&nbsp;IN', info_label_style),
                Paragraph(f"{session_name} B.S.", info_value_style),
                Paragraph('ARE&nbsp;GIVEN&nbsp;BELOW:', info_label_style)
            ]
        ], colWidths=[7.0*cm, 2.5*cm, 9.9*cm], hAlign='LEFT')
        row3.setStyle(ts_info)
        
        story.append(row1)
        story.append(row2)
        story.append(row3)
        story.append(Spacer(1, 4*mm))
        
        # 3. Grading Table
        th_style = ParagraphStyle('THNEB', fontSize=8.5, fontName='Times-Bold', alignment=TA_CENTER)
        
        table_data = [[
            Paragraph("SUBJECT<br/>CODE", th_style),
            Paragraph("SUBJECT", th_style),
            Paragraph("CREDIT<br/>HOUR", th_style),
            Paragraph("GRADE POINT<br/>(GP)", th_style),
            Paragraph("GRADE", th_style),
            Paragraph("FINAL<br/>GRADE", th_style),
        ]]
        
        cell_style = ParagraphStyle('CellNEB', fontSize=8.5, fontName='Times-Bold', alignment=TA_CENTER)
        cell_left_style = ParagraphStyle('CellLeftNEB', fontSize=8.5, fontName='Times-Bold', alignment=TA_LEFT)
        
        span_rules = []
        row_idx = 1
        
        for me in self.mark_entries:
            subj = me.subject
            sr = getattr(me, 'subject_result', None)
            if not subj.affects_gpa:
                continue
                
            if subj.has_practical:
                code_th = subj.code
                name_th = subj.name.upper() + " (TH)"
                ch_th = f"{subj.theory_credit_hour:.2f}"
                
                code_in = subj.practical_code or (subj.code + "P")
                name_in = subj.name.upper() + " (IN)"
                ch_in = f"{subj.practical_credit_hour:.2f}"
                
                if me.special_value:
                    val_display = me.get_special_value_display()
                    row_th = [
                        Paragraph(code_th, cell_style), Paragraph(name_th, cell_left_style), Paragraph(ch_th, cell_style),
                        Paragraph(val_display, cell_style), Paragraph(val_display, cell_style),
                        Paragraph(val_display, cell_style)
                    ]
                    row_in = [
                        Paragraph(code_in, cell_style), Paragraph(name_in, cell_left_style), Paragraph(ch_in, cell_style),
                        Paragraph(val_display, cell_style), Paragraph(val_display, cell_style), ""
                    ]
                else:
                    th_gp = f"{sr.theory_grade_point:.2f}" if sr and sr.theory_grade_point is not None else "0.00"
                    th_g = sr.theory_grade if sr and sr.theory_grade else "NG"
                    
                    in_gp = f"{sr.internal_grade_point:.2f}" if sr and sr.internal_grade_point is not None else "0.00"
                    in_g = sr.internal_grade if sr and sr.internal_grade else "NG"
                    
                    fg = sr.grade if sr and sr.grade else "NG"
                    
                    row_th = [
                        Paragraph(code_th, cell_style), Paragraph(name_th, cell_left_style), Paragraph(ch_th, cell_style),
                        Paragraph(th_gp, cell_style), Paragraph(th_g, cell_style),
                        Paragraph(fg, cell_style)
                    ]
                    row_in = [
                        Paragraph(code_in, cell_style), Paragraph(name_in, cell_left_style), Paragraph(ch_in, cell_style),
                        Paragraph(in_gp, cell_style), Paragraph(in_g, cell_style),
                        ""
                    ]
                table_data.append(row_th)
                table_data.append(row_in)
                span_rules.append(('SPAN', (5, row_idx), (5, row_idx + 1)))
                row_idx += 2
            else:
                code = subj.code
                name = subj.name.upper() + " (TH)"
                ch = f"{subj.theory_credit_hour:.2f}"
                if me.special_value:
                    val_display = me.get_special_value_display()
                    row = [
                        Paragraph(code, cell_style), Paragraph(name, cell_left_style), Paragraph(ch, cell_style),
                        Paragraph(val_display, cell_style), Paragraph(val_display, cell_style),
                        Paragraph(val_display, cell_style)
                    ]
                else:
                    gp = f"{sr.grade_point:.2f}" if sr and sr.grade_point is not None else "0.00"
                    g = sr.grade if sr and sr.grade else "NG"
                    fg = g
                    row = [
                        Paragraph(code, cell_style), Paragraph(name, cell_left_style), Paragraph(ch, cell_style),
                        Paragraph(gp, cell_style), Paragraph(g, cell_style),
                        Paragraph(fg, cell_style)
                    ]
                table_data.append(row)
                row_idx += 1
                
        # Extra credit
        non_credit_entries = [me for me in self.mark_entries if not me.subject.affects_gpa]
        if non_credit_entries:
            table_data.append([Paragraph("EXTRA CREDIT SUBJECT", cell_left_style), "", "", "", "", ""])
            span_rules.append(('SPAN', (0, row_idx), (-1, row_idx)))
            span_rules.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f8f9fa')))
            row_idx += 1
            for me in non_credit_entries:
                subj = me.subject
                sr = getattr(me, 'subject_result', None)
                if subj.has_practical:
                    code_th = subj.code
                    name_th = subj.name.upper() + " (TH)"
                    ch_th = f"{subj.theory_credit_hour:.2f}"
                    
                    code_in = subj.practical_code or (subj.code + "P")
                    name_in = subj.name.upper() + " (IN)"
                    ch_in = f"{subj.practical_credit_hour:.2f}"
                    
                    if me.special_value:
                        val_display = me.get_special_value_display()
                        row_th = [
                            Paragraph(code_th, cell_style), Paragraph(name_th, cell_left_style), Paragraph(ch_th, cell_style),
                            Paragraph(val_display, cell_style), Paragraph(val_display, cell_style),
                            Paragraph(val_display, cell_style)
                        ]
                        row_in = [
                            Paragraph(code_in, cell_style), Paragraph(name_in, cell_left_style), Paragraph(ch_in, cell_style),
                            Paragraph(val_display, cell_style), Paragraph(val_display, cell_style), ""
                        ]
                    else:
                        th_gp = f"{sr.theory_grade_point:.2f}" if sr and sr.theory_grade_point is not None else "0.00"
                        th_g = sr.theory_grade if sr and sr.theory_grade else "NG"
                        
                        in_gp = f"{sr.internal_grade_point:.2f}" if sr and sr.internal_grade_point is not None else "0.00"
                        in_g = sr.internal_grade if sr and sr.internal_grade else "NG"
                        
                        fg = sr.grade if sr and sr.grade else "NG"
                        
                        row_th = [
                            Paragraph(code_th, cell_style), Paragraph(name_th, cell_left_style), Paragraph(ch_th, cell_style),
                            Paragraph(th_gp, cell_style), Paragraph(th_g, cell_style),
                            Paragraph(fg, cell_style)
                        ]
                        row_in = [
                            Paragraph(code_in, cell_style), Paragraph(name_in, cell_left_style), Paragraph(ch_in, cell_style),
                            Paragraph(in_gp, cell_style), Paragraph(in_g, cell_style),
                            ""
                        ]
                    table_data.append(row_th)
                    table_data.append(row_in)
                    span_rules.append(('SPAN', (5, row_idx), (5, row_idx + 1)))
                    row_idx += 2
                else:
                    code = subj.code
                    name = subj.name.upper() + " (TH)"
                    ch = f"{subj.theory_credit_hour:.2f}"
                    if me.special_value:
                        val_display = me.get_special_value_display()
                        row = [
                            Paragraph(code, cell_style), Paragraph(name, cell_left_style), Paragraph(ch, cell_style),
                            Paragraph(val_display, cell_style), Paragraph(val_display, cell_style),
                            Paragraph(val_display, cell_style)
                        ]
                    else:
                        gp = f"{sr.grade_point:.2f}" if sr and sr.grade_point is not None else "0.00"
                        g = sr.grade if sr and sr.grade else "NG"
                        fg = g
                        row = [
                            Paragraph(code, cell_style), Paragraph(name, cell_left_style), Paragraph(ch, cell_style),
                            Paragraph(gp, cell_style), Paragraph(g, cell_style),
                            Paragraph(fg, cell_style)
                        ]
                    table_data.append(row)
                    row_idx += 1
        
        # GPA row
        if self.result:
            gpa_text = f"GRADE POINT AVERAGE (GPA): {self.result.overall_gpa:.2f}" if self.result.overall_gpa is not None else "0.00"
            gpa_para = Paragraph(gpa_text, ParagraphStyle('GPA', fontSize=9, fontName='Times-Bold', alignment=TA_RIGHT, textColor=colors.HexColor('#1e3a8a')))
            table_data.append([gpa_para, "", "", "", "", ""])
            span_rules.append(('SPAN', (0, row_idx), (4, row_idx)))
            span_rules.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f8f9fa')))
        
        # col_widths = [1.8*cm, 9.0*cm, 1.5*cm, 2.0*cm, 1.5*cm, 3.6*cm] (Total 19.4cm)
        col_widths = [1.8*cm, 9.5*cm, 1.8*cm, 2.3*cm, 1.8*cm, 2.2*cm]
        main_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        ts = [
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ] + span_rules
        main_table.setStyle(TableStyle(ts))
        
        story.append(main_table)
        story.append(Spacer(1, 15*mm))
        
        # Signatures
        sig_style = ParagraphStyle('Sig', fontSize=9, fontName='Times-Bold', alignment=TA_CENTER)
        sig_line = HRFlowable(width="80%", thickness=1, color=colors.black, spaceBefore=0, spaceAfter=2)
        sig_table = Table([
            [sig_line, sig_line, sig_line],
            [Paragraph("PREPARED BY", sig_style), Paragraph("CHECKED BY", sig_style), Paragraph("HEAD TEACHER", sig_style)]
        ], colWidths=[6.4*cm, 6.4*cm, 6.4*cm])
        story.append(sig_table)
        
        story.append(Spacer(1, 3*mm))
        
        from datetime import date
        date_para = Paragraph(f"Date of Issue: &nbsp;&nbsp;&nbsp;{date.today().strftime('%Y/%m/%d')}", ParagraphStyle('Date', fontSize=9, fontName='Times-Bold', leftIndent=15))
        story.append(date_para)
        
        story.append(Spacer(1, 3*mm))
        
        # Notes
        note_style = ParagraphStyle('Note', fontSize=8.5, fontName='Times-Roman', textColor=colors.HexColor('#1e3a8a'), spaceBefore=2, spaceAfter=2)
        story.append(Paragraph("NOTE: ONE CREDIT HOUR EQUALS TO 32 WORKING HOURS", note_style))
        story.append(Paragraph("INTERNAL(IN): THIS COVERS THE PARTICIPATION, PRACTICAL/PROJECT WORKS, COMMUNITY WORKS, INTERNSHIP, PRESENTATIONS, TERMINAL EXAMINATIONS.", note_style))
        story.append(Paragraph("THEORY(TH): THIS COVERS WRITTEN EXTERNAL EXAMINATION", note_style))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph("ABS = ABSENT &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; W = WITHHELD", note_style))
        
        return story

    def generate(self):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8*cm,
            leftMargin=0.8*cm,
            topMargin=0.8*cm,
            bottomMargin=0.8*cm,
        )
        
        story = self.get_story()
        
        # Outer Border wrapper
        def add_border(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(2)
            canvas.rect(0.4*cm, 0.4*cm, A4[0]-0.8*cm, A4[1]-0.8*cm)
            canvas.restoreState()
            
        doc.build(story, onFirstPage=add_border, onLaterPages=add_border)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes


class NEB11ClassMarksheetsPDFGenerator:
    """Generates an NEB 11 merged PDF marksheet for all students in a class."""

    def __init__(self, school, exam, cls_obj, student_results, student_mark_map):
        self.school = school
        self.exam = exam
        self.cls_obj = cls_obj
        self.student_results = student_results
        self.student_mark_map = student_mark_map

    def generate(self):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8*cm,
            leftMargin=0.8*cm,
            topMargin=0.8*cm,
            bottomMargin=0.8*cm,
        )
        
        story = []
        from reportlab.platypus.flowables import PageBreak
        
        # Helper function for outer border
        def add_border(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(2)
            canvas.rect(0.4*cm, 0.4*cm, A4[0]-0.8*cm, A4[1]-0.8*cm)
            canvas.restoreState()

        for idx, sr in enumerate(self.student_results):
            student = sr.student
            mark_entries = self.student_mark_map.get(student.id, [])
            
            single_gen = NEB11MarksheetPDFGenerator(self.school, self.exam, student, sr, mark_entries)
            
            # Wrap the entire marksheet inside a KeepTogether to prevent page breaks in the middle
            student_story = single_gen.get_story()
            story.append(KeepTogether(student_story))
            
            if idx < len(self.student_results) - 1:
                story.append(PageBreak())

        doc.build(story, onFirstPage=add_border, onLaterPages=add_border)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
