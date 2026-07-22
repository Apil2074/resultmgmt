from .base import *

class LedgerPDFGenerator:
    """
    Generates a landscape grade ledger PDF matching the standard 4-row Nepalese layout.
    The ledger typically contains multiple students across multiple pages, with subjects split horizontally if they exceed page width.
    """

    def __init__(self, school, exam, cls, subjects, student_results, mark_map):
        """
        Initialize the Ledger generator with context data.
        
        Args:
            school: School instance
            exam: Exam instance
            cls: Class instance
            subjects: Iterable of subjects to be included in the ledger
            student_results: Iterable of student results
            mark_map: Dictionary mapping student_id to their list of MarkEntry objects
        """
        self.school = school
        self.exam = exam
        self.cls = cls
        self.subjects = sorted(list(subjects), key=lambda x: x.order)
        self.student_results = list(student_results)
        self.mark_map = mark_map

    def generate(self):
        """
        Build and return the PDF document as a bytes object.
        """
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
        """
        Build the ReportLab flowable story.
        """
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
        LEFT_WIDTH = 6.7 * cm
        RIGHT_WIDTH = 6.2 * cm
        
        pages = []
        current_page_subjects = []
        current_width = LEFT_WIDTH
        
        for subj in self.subjects:
            try:
                ms = subj
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
            ]
            header2 = ['', '', '', '']
            header3 = ['', '', '', '']
            header4 = ['', '', '', '']
            
            col_idx = 4
            span_rules = []
            
            # Student info columns span 4 rows vertically
            span_rules.append(('SPAN', (0, 0), (0, 3))) # SN
            span_rules.append(('SPAN', (1, 0), (1, 3))) # Symbol No
            span_rules.append(('SPAN', (2, 0), (2, 3))) # REG NO
            span_rules.append(('SPAN', (3, 0), (3, 3))) # Student Name

            for subj in page_subjs:
                try:
                    ms = subj
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
                    header4.append(Paragraph('GPA', h_sub_style))
                    header4.append(Paragraph('Grade', h_sub_style))
                else:
                    header4.append(Paragraph('Th', h_sub_style))
                    header4.append(Paragraph('Th GP', h_sub_style))
                    header4.append(Paragraph('GPA', h_sub_style))
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
                    ms = s
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
            
            col_widths = [0.5*cm, 1.2*cm, 2.0*cm, 3.0*cm] # Left columns (sum to 6.7 cm)
            for s in page_subjs:
                try:
                    ms = s
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

            # Pre-compute attendance for all students (avoids O(students × subjects) inner loop)
            attendance_map = {}
            if include_summary:
                for sr in self.student_results:
                    sid = sr.student.id
                    total_present = 0
                    total_days = 0
                    has_attendance = False
                    for subj in self.subjects:
                        m_entry = self.mark_map.get((sid, subj.id))
                        if m_entry:
                            if m_entry.present_days is not None:
                                total_present = max(total_present, m_entry.present_days)
                                has_attendance = True
                            if m_entry.total_days:
                                total_days = max(total_days, m_entry.total_days)
                    if has_attendance and total_days > 0:
                        attendance_map[sid] = f"{round((total_present / total_days) * 100, 1)}%"

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
                ]
                
                for subj in page_subjs:
                    try:
                        ms = subj
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
                    att = attendance_map.get(student.id, '—')
                        
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
            
            for idx in range(4, col_idx - (6 if include_summary else 0)):
                t_styles.append(('BACKGROUND', (idx, 0), (idx, 0), colors.HexColor('#e2e8f0')))
                
            # Color AVG GPA and Grade columns
            col_c = 4
            for subj in page_subjs:
                try:
                    ms = subj
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

