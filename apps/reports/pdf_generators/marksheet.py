from .base import *
from .base import _get_logo_image

class MarksheetPDFGenerator:
    """Generates a professional individual marksheet PDF matching the Nepalese grade-sheet template."""

    # Grade remarks mapping (class-level constant — shared across all instances)
    GRADE_REMARKS = {
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

    def __init__(self, school, exam, student, result, mark_entries):
        """
        Initialize the generator with context objects required for the marksheet.
        
        Args:
            school: School instance
            exam: Exam instance
            student: Student instance
            result: Result instance containing aggregate scores
            mark_entries: Iterable of MarkEntry objects for this student
        """
        self.school = school
        self.exam = exam
        self.student = student
        self.result = result
        # Sort mark entries by subject order
        self.mark_entries = sorted(list(mark_entries), key=lambda x: x.subject.order if x.subject else 0)
        
        # Cache the logo path once to avoid repeated disk checks
        self._logo_path = None
        try:
            if school.logo and os.path.exists(school.logo.path):
                self._logo_path = school.logo.path
        except Exception:
            pass
        
        # Enrich subject result remarks
        for me in self.mark_entries:
            sr = getattr(me, 'subject_result', None)
            if sr:
                sr.theory_remark = self.GRADE_REMARKS.get(sr.theory_grade, '—') if sr.theory_grade else '—'
                sr.internal_remark = self.GRADE_REMARKS.get(sr.internal_grade, '—') if sr.internal_grade else '—'
                sr.overall_remark = self.GRADE_REMARKS.get(sr.grade, '—') if sr.grade else '—'
                
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

        # Pre-build reusable ParagraphStyles once (avoids re-creating per _build_story call)
        self._styles = self._create_styles()

    @staticmethod
    def _create_styles():
        """Create and return all ParagraphStyle objects used in the marksheet, once."""
        return {
            'school_name': ParagraphStyle(
                'SchoolNameNEB', fontSize=22, fontName='Times-Bold',
                alignment=TA_CENTER, textColor=colors.black,
                leading=26, spaceAfter=4
            ),
            'address': ParagraphStyle(
                'AddressNEB', fontSize=12, fontName='Times-Roman',
                alignment=TA_CENTER, textColor=colors.black,
                leading=16, spaceAfter=4
            ),
            'see': ParagraphStyle(
                'SEENEB', fontSize=14, fontName='Times-Bold',
                alignment=TA_CENTER, textColor=colors.black, spaceBefore=4, spaceAfter=4,
                leading=18
            ),
            'gs': ParagraphStyle(
                'GSNEB', fontSize=16, fontName='Times-Bold',
                alignment=TA_CENTER, textColor=colors.HexColor('#1e3a8a'),
                leading=20
            ),
            'info_label': ParagraphStyle(
                'InfoLabel', fontSize=9, fontName='Times-Bold',
                textColor=colors.HexColor('#1e3a8a')
            ),
            'info_value': ParagraphStyle(
                'InfoValue', fontSize=9.5, fontName='Times-Bold',
                textColor=colors.HexColor('#0f172a')
            ),
            'nested_label': ParagraphStyle(
                'NestedLabel', fontSize=9, fontName='Times-Bold',
                textColor=colors.HexColor('#1e3a8a')
            ),
            'nested_val': ParagraphStyle(
                'NestedVal', fontSize=9.5, fontName='Times-Bold',
                textColor=colors.HexColor('#0f172a'), alignment=TA_CENTER
            ),
            'th': ParagraphStyle(
                'TableHeader', fontSize=7.5, fontName='Times-Bold',
                textColor=colors.HexColor('#1e3a8a'), alignment=TA_CENTER
            ),
            'th_left': ParagraphStyle(
                'TableHeaderLeft', fontSize=7.5, fontName='Times-Bold',
                textColor=colors.HexColor('#1e3a8a'), alignment=TA_LEFT
            ),
            'cell': ParagraphStyle(
                'TableCell', fontSize=7.5, fontName='Times-Bold', alignment=TA_CENTER
            ),
            'cell_bold': ParagraphStyle(
                'TableCellBold', fontSize=7.5, fontName='Times-Bold', alignment=TA_CENTER
            ),
            'cell_left': ParagraphStyle(
                'TableCellLeft', fontSize=7.5, fontName='Times-Bold', alignment=TA_LEFT
            ),
            'cell_danger': ParagraphStyle(
                'TableCellDanger', fontSize=7.5, fontName='Times-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#EF4444')
            ),
            'cell_fg': ParagraphStyle(
                'TableCellFG', fontSize=8.5, fontName='Times-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#1d4ed8')
            ),
            'footer_label': ParagraphStyle(
                'FooterLabel', fontName='Times-Bold', fontSize=8.5,
                textColor=colors.HexColor('#1e3a8a'), alignment=TA_RIGHT
            ),
            'th_non_credit': ParagraphStyle(
                'ThNonCredit', fontName='Times-Bold', fontSize=8.5,
                textColor=colors.HexColor('#1e3a8a'), alignment=TA_LEFT
            ),
            'note_title': ParagraphStyle(
                'NoteTitle', fontSize=10.0, fontName='Times-Bold',
                textColor=colors.HexColor('#1e293b'), spaceAfter=1
            ),
            'note_text': ParagraphStyle(
                'NoteText', fontSize=10.0, fontName='Times-Roman',
                textColor=colors.HexColor('#475569'), leading=8, spaceAfter=5
            ),
            'legend_th': ParagraphStyle(
                'LegendTh', fontSize=6.5, fontName='Times-Bold',
                textColor=colors.black, alignment=TA_CENTER
            ),
            'legend_td': ParagraphStyle(
                'LegendTd', fontSize=6.5, fontName='Times-Roman',
                textColor=colors.black, alignment=TA_CENTER
            ),
            'legend_td_bold': ParagraphStyle(
                'LegendTdBold', fontSize=6.5, fontName='Times-Bold',
                textColor=colors.black, alignment=TA_CENTER
            ),
            'att_label': ParagraphStyle(
                'AttLabel', fontSize=8, fontName='Times-Bold',
                textColor=colors.HexColor('#1e293b')
            ),
            'att_val': ParagraphStyle(
                'AttVal', fontSize=8, fontName='Times-Bold',
                textColor=colors.black, alignment=TA_CENTER
            ),
            'sig_label': ParagraphStyle(
                'SigLabel', fontSize=8, fontName='Times-Bold',
                textColor=colors.HexColor('#1e293b'), alignment=TA_CENTER
            ),
        }

    def generate(self):
        """
        Build and return the PDF document as a bytes object.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8*cm,
            leftMargin=0.8*cm,
            topMargin=0.2*cm,
            bottomMargin=0.2*cm,
        )
        story = self._build_story()
        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return buffer.getvalue()

    def _header_footer(self, canvas_obj, doc):
        """
        Callback to draw the page header and footer.
        Adds a double border around the page and a faint logo watermark in the center.
        Uses cached logo path to avoid repeated disk reads.
        """
        canvas_obj.saveState()
        # Double border around the page in Navy
        navy_color = colors.HexColor('#1E3A8A')
        canvas_obj.setStrokeColor(navy_color)
        canvas_obj.setLineWidth(1)
        canvas_obj.rect(0.4*cm, 0.4*cm, A4[0] - 0.8*cm, A4[1] - 0.8*cm)
        
        # Faint Logo Watermark in the center of the page (uses cached path)
        try:
            if self._logo_path:
                logo_w = 9*cm
                logo_h = 9*cm
                canvas_obj.setFillAlpha(0.04)
                canvas_obj.setStrokeAlpha(0.04)
                canvas_obj.drawImage(self._logo_path, (A4[0]-logo_w)/2, (A4[1]-logo_h)/2, width=logo_w, height=logo_h, mask='auto')
        except Exception:
            pass
        
        # Reset alphas and draw Footer text
        canvas_obj.restoreState()
        canvas_obj.saveState()
        canvas_obj.setFont('Times-Roman', 8)
        canvas_obj.setFillColor(colors.HexColor('#64748b'))
        canvas_obj.drawString(0.9*cm, 0.4*cm, self.school.name)
        canvas_obj.restoreState()

    def _build_story(self):
        """
        Build the ReportLab flowable story.
        Uses pre-built styles from self._styles for performance.
        """
        story = []
        s = self._styles  # shorthand for cached styles

        # 1. School Header
        school_info = [
            Paragraph(self.school.name, s['school_name']),
            Paragraph(self.school.address, s['address']),
        ]
        if self.school.establishment_year:
            school_info.append(Paragraph(f"Estd: {self.school.establishment_year}", s['address']))
        school_info.extend([
        
            Paragraph("<u>GRADE-SHEET</u>", s['gs'])
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
        
        # 3. Student Info Rows (Using NEB template layout)
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
        
        class_name = self.student.class_obj.name.upper() if self.student.class_obj else '—'
        
        row2 = Table([
            [
                Paragraph('REGISTRATION&nbsp;NO.:', info_label_style), Paragraph(reg_no, info_value_style),
                Paragraph('SYMBOL&nbsp;NO.:', info_label_style), Paragraph(sym_no, info_value_style),
                Paragraph('CLASS:', info_label_style), Paragraph(class_name, info_value_style)
            ]
        ], colWidths=[3.6*cm, 3.5*cm, 2.4*cm, 3.0*cm, 1.5*cm, 5.4*cm], hAlign='LEFT')
        row2.setStyle(ts_info)
        
        exam_name = self.exam.name.upper() if self.exam else '—'
        bs_year = self.exam.start_date if self.exam and self.exam.start_date else session_name
        
        ad_year = self.exam.end_date if self.exam and self.exam.end_date else ""
        ad_label = "A.D." if ad_year else ""

        row3_data = [
            [
                Paragraph('IN&nbsp;THE:', info_label_style),
                Paragraph(exam_name, info_value_style),
                Paragraph('HELD&nbsp;IN:', info_label_style),
                Paragraph(bs_year, info_value_style),
                Paragraph('B.S.', info_label_style),
                Paragraph(ad_year, info_value_style),
                Paragraph(ad_label, info_label_style),
                Paragraph('ARE&nbsp;GIVEN&nbsp;BELOW:', info_label_style)
            ]
        ]
        row3 = Table(row3_data, colWidths=[1.3*cm, 8.2*cm, 1.6*cm, 1.2*cm, 0.8*cm, 1.2*cm, 0.8*cm, 4.3*cm], hAlign='LEFT')
        row3.setStyle(ts_info)

        story.append(row1)
        story.append(row2)
        story.append(row3)
        story.append(Spacer(1, 4*mm))
        
        # 4. Grading Table (styles from cached self._styles)
        th_style = s['th']
        th_left_style = s['th_left']
        cell_style = s['cell']
        cell_bold_style = s['cell_bold']
        cell_left_style = s['cell_left']
        cell_danger_style = s['cell_danger']
        cell_fg_style = s['cell_fg']
        
        table_headers = [
            Paragraph('SUBJECT CODE', th_style),
            Paragraph('SUBJECTS', th_left_style),
            Paragraph('CREDIT HOUR (CH)', th_style),
            Paragraph('GRADE POINT (GP)', th_style),
            Paragraph('GRADE', th_style),
            Paragraph('FINAL GRADE (FG)', th_style),
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
                span_rules.append(('LINEBELOW', (0, row_idx + 1), (-1, row_idx + 1), 0.5, colors.HexColor('#475569')))
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
                span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
                row_idx += 1
                
        if len(table_data) == 1:
            table_data.append([
                Paragraph('No marks recorded.', cell_style),
                '', '', '', '', ''
            ])
            span_rules.append(('SPAN', (0, row_idx), (5, row_idx)))
            span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
            row_idx += 1
            
        if self.result:
            footer_label_style = s['footer_label']
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
            span_rules.append(('SPAN', (4, row_idx), (5, row_idx)))
            span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
            span_rules.append(('SPAN', (0, row_idx + 1), (3, row_idx + 1)))
            span_rules.append(('SPAN', (4, row_idx + 1), (5, row_idx + 1)))
            span_rules.append(('LINEBELOW', (0, row_idx + 1), (-1, row_idx + 1), 0.5, colors.HexColor('#475569')))
            row_idx += 2

        if non_credit_mark_entries:
            th_non_credit_style = s['th_non_credit']
            row_header = [
                Paragraph('NON-CREDIT SUBJECTS', th_non_credit_style),
                '', '', '', '', ''
            ]
            table_data.append(row_header)
            span_rules.append(('SPAN', (0, row_idx), (5, row_idx)))
            span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
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
                    span_rules.append(('LINEBELOW', (0, row_idx + 1), (-1, row_idx + 1), 0.5, colors.HexColor('#475569')))
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
                    span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
                    row_idx += 1
            
        col_widths = [2.8*cm, 6.4*cm, 2.5*cm, 2.5*cm, 2.4*cm, 2.8*cm]
        marks_table = Table(table_data, colWidths=col_widths)
        
        # Calculate dynamic padding based on number of subjects
        num_subjects = len(self.mark_entries)
        dynamic_padding = max(1, 1 + int((10 - num_subjects) * 1.4))

        table_style_commands = [
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#475569')),
            ('LINEBEFORE', (1, 0), (-1, -1), 0.5, colors.HexColor('#475569')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#475569')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), dynamic_padding),
            ('BOTTOMPADDING', (0, 0), (-1, -1), dynamic_padding),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (5, 1), (5, -1), colors.HexColor('#F8FAFC')),
        ]
        for rule in span_rules:
            table_style_commands.append(rule)
            
        marks_table.setStyle(TableStyle(table_style_commands))
        story.append(marks_table)
        story.append(Spacer(1, 3*mm))
        
        # 5. Bottom Meta & Legend Block (styles from cached self._styles)
        note_title_style = s['note_title']
        note_text_style = s['note_text']
        
        note_flowables = [
            Paragraph('NOTE :', note_title_style),
            Paragraph(' One credit hour equals 32 working hours.', note_text_style),
            Paragraph(' Internal (In): This covers the participation, practical/project works, community works, internship, presentations and terminal examinations.', note_text_style),
            Paragraph(' Theory (Th): This covers written external examination.', note_text_style),
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
        
        legend_th_style = s['legend_th']
        legend_td_style = s['legend_td']
        legend_td_bold_style = s['legend_td_bold']
        
        legend_headers = [
            Paragraph('Grade Point', legend_th_style),
            Paragraph('Grade', legend_th_style),
            Paragraph('Interval', legend_th_style),
        ]
        
        legend_rows = [
            [Paragraph('4.0', legend_td_style), Paragraph('A+', legend_td_bold_style), Paragraph('90 To 100', legend_td_style)],
            [Paragraph('3.6', legend_td_style), Paragraph('A', legend_td_bold_style), Paragraph('80 To Below 90', legend_td_style)],
            [Paragraph('3.2', legend_td_style), Paragraph('B+', legend_td_bold_style), Paragraph('70 To Below 80', legend_td_style)],
            [Paragraph('2.8', legend_td_style), Paragraph('B', legend_td_bold_style), Paragraph('60 To Below 70', legend_td_style)],
            [Paragraph('2.4', legend_td_style), Paragraph('C+', legend_td_bold_style), Paragraph('50 To Below 60', legend_td_style)],
            [Paragraph('2.0', legend_td_style), Paragraph('C', legend_td_bold_style), Paragraph('40 To Below 50', legend_td_style)],
            [Paragraph('1.6', legend_td_style), Paragraph('D', legend_td_bold_style), Paragraph('35 To Below 40', legend_td_style)],
            [Paragraph('0.0', legend_td_style), Paragraph('NG', legend_td_bold_style), Paragraph('0 To Below 35', legend_td_style)],
        ]
        
        legend_table_data = [legend_headers] + legend_rows
        legend_table = Table(legend_table_data, colWidths=[2.2*cm, 2.0*cm, 4.0*cm])
        legend_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        att_label_style = s['att_label']
        att_val_style = s['att_val']
        
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
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        
        left_flowables = [
            att_table,
            Spacer(1, 2*mm),
            issue_table
        ]
        
        date_att_table = Table([[left_flowables]], colWidths=[19.4*cm])
        date_att_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(date_att_table)
        story.append(Spacer(1, 1.5*cm))  # Space before signatures
        
        # 6. Signatures (style from cached self._styles)
        sig_label_style = s['sig_label']
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
        story.append(Spacer(1, 1.0*cm))  # Space before note and legend
        
        # 7. Note and Legend (moved below signatures)
        bottom_sections_table = Table([[note_box, legend_table]], colWidths=[11.2*cm, 8.2*cm])
        bottom_sections_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(bottom_sections_table)
        
        return story


class ClassMarksheetsPDFGenerator:
    """
    Generates a single merged PDF containing marksheets for all students in a given class.
    Each student's marksheet will appear on a new page.
    """

    def __init__(self, school, exam, cls, student_results, student_mark_map):
        """
        Initialize the Class Marksheets generator.
        
        Args:
            school: School instance
            exam: Exam instance
            cls: Class instance
            student_results: Iterable of student results for the class
            student_mark_map: Dictionary mapping student_id to their MarkEntry objects
        """
        self.school = school
        self.exam = exam
        self.cls = cls
        self.student_results = student_results
        self.student_mark_map = student_mark_map

    def generate(self):
        """
        Build and return the PDF document as a bytes object.
        """
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
        
        header_footer_ref = None
        for idx, sr in enumerate(self.student_results):
            student = sr.student
            mark_entries = self.student_mark_map.get(student.id, [])
            
            student_generator = MarksheetPDFGenerator(self.school, self.exam, student, sr, mark_entries)
            student_story = student_generator._build_story()
            
            # Save reference to the first generator for header/footer reuse (avoids creating a duplicate)
            if header_footer_ref is None:
                header_footer_ref = student_generator
            
            story.extend(student_story)
            if idx < len(self.student_results) - 1:
                story.append(PageBreak())
                
        # Re-use the header/footer drawing method from the first student's generator
        if header_footer_ref:
            doc.build(story, onFirstPage=header_footer_ref._header_footer, onLaterPages=header_footer_ref._header_footer)
        else:
            doc.build(story)
            
        return buffer.getvalue()

