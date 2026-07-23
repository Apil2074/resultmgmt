from .base import *
from .base import _get_logo_image

from .marksheet import MarksheetPDFGenerator

class NEB11MarksheetPDFGenerator(MarksheetPDFGenerator):
    """
    Generates an NEB Grade 11 format marksheet.
    Inherits from MarksheetPDFGenerator but overrides the get_story and generate methods for the specific layout.
    """
    
    def get_story(self):
        """
        Builds the reportlab story (flowables) for the NEB 11 marksheet.
        """
        story = []
        
        # 1. School Header
        sfs = getattr(self, 'school_name_font_size', 22.0)
        bls = getattr(self, 'line_spacing', 1.2)
        school_name_style = ParagraphStyle(
            'SchoolNameNEB', fontSize=sfs, fontName='Times-Bold',
            alignment=TA_CENTER, textColor=colors.black,
            leading=sfs * 1.2, spaceAfter=4
        )
        address_style = ParagraphStyle(
            'AddressNEB', fontSize=14, fontName='Times-Roman',
            alignment=TA_CENTER, textColor=colors.black,
            leading=16, spaceAfter=4
        )
        see_style = ParagraphStyle(
            'SEENEB', fontSize=13, fontName='Times-Bold',
            alignment=TA_CENTER, textColor=colors.black, spaceBefore=2, spaceAfter=2,
            leading=18
        )
        gs_style = ParagraphStyle(
            'GSNEB', fontSize=14, fontName='Times-Bold',
            alignment=TA_CENTER, textColor=colors.HexColor('#1e3a8a'),
            leading=20,spaceAfter=1
        )
        
        school_info = [
            Paragraph(self.school.name, school_name_style),
            Paragraph(self.school.address, address_style),
        ]
        if self.school.establishment_year:
            school_info.append(Paragraph(f"Estd: {self.school.establishment_year}", address_style))
        if getattr(self, 'exam_title', ''):
            school_info.append(Paragraph(self.exam_title.upper(), see_style))
        school_info.extend([
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
        
        cell_style = ParagraphStyle('CellNEB', fontSize=9, fontName='Times-Bold', alignment=TA_CENTER)
        cell_left_style = ParagraphStyle('CellLeftNEB', fontSize=9, fontName='Times-Bold', alignment=TA_LEFT)
        
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
                span_rules.append(('LINEBELOW', (0, row_idx + 1), (-1, row_idx + 1), 0.5, colors.HexColor('#475569')))
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
                span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
                row_idx += 1
                
        # Extra credit
        non_credit_entries = [me for me in self.mark_entries if not me.subject.affects_gpa]
        if non_credit_entries:
            table_data.append([Paragraph("EXTRA CREDIT SUBJECT", cell_left_style), "", "", "", "", ""])
            span_rules.append(('SPAN', (0, row_idx), (-1, row_idx)))
            span_rules.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f8f9fa')))
            span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
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
                    span_rules.append(('LINEBELOW', (0, row_idx + 1), (-1, row_idx + 1), 0.5, colors.HexColor('#475569')))
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
                    span_rules.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor('#475569')))
                    row_idx += 1
        
        # GPA row
        if self.result:
            if self.result.is_pass is False:
                gpa_val = "NG"
            else:
                gpa_val = f"{self.result.overall_gpa:.2f}" if self.result.overall_gpa is not None else "0.00"
                
            gpa_label = Paragraph("GRADE POINT AVERAGE (GPA)", ParagraphStyle('GPALabel', fontSize=9, fontName='Times-Bold', alignment=TA_RIGHT, textColor=colors.HexColor('#1e3a8a')))
            gpa_para = Paragraph(gpa_val, ParagraphStyle('GPAVal', fontSize=9, fontName='Times-Bold', alignment=TA_CENTER, textColor=colors.HexColor('#1e3a8a')))
            
            table_data.append([gpa_label, "", "", gpa_para, "", ""])
            span_rules.append(('SPAN', (0, row_idx), (2, row_idx)))
            span_rules.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f8f9fa')))
        
        # col_widths = [1.8*cm, 9.0*cm, 1.5*cm, 2.0*cm, 1.5*cm, 3.6*cm] (Total 19.4cm)
        col_widths = [1.8*cm, 9.5*cm, 1.8*cm, 2.3*cm, 1.8*cm, 2.2*cm]
        main_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Calculate dynamic padding based on number of subjects
        num_subjects = len(self.mark_entries)
        # When 10 subjects, padding is 1. Increases linearly as subject count drops.
        base_pad = max(1, 1 + int((10 - num_subjects) * 1.5))
        dynamic_padding = base_pad + (getattr(self, 'line_spacing', 1.0) - 1.0) * 10

        ts = [
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#475569')),
            ('LINEBEFORE', (1, 0), (-1, -1), 0.5, colors.HexColor('#475569')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#475569')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), dynamic_padding),
            ('TOPPADDING', (0, 0), (-1, -1), dynamic_padding),
        ] + span_rules
        main_table.setStyle(TableStyle(ts))
        
        story.append(main_table)
        story.append(Spacer(1, 15*mm))
        
        # Signatures
        sig_style = ParagraphStyle('Sig', fontSize=9, fontName='Times-Bold', alignment=TA_CENTER)
        sig_line = HRFlowable(width="75%", thickness=1, color=colors.black, spaceBefore=0, spaceAfter=2, hAlign='CENTER')
        sig_table = Table([
            [sig_line, sig_line, sig_line],
            [Paragraph("PREPARED BY", sig_style), Paragraph("CHECKED BY", sig_style), Paragraph("HEAD TEACHER", sig_style)]
        ], colWidths=[6.3*cm, 6.3*cm, 6.3*cm])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(sig_table)
        
        story.append(Spacer(1, 3*mm))
        
        from datetime import date
        if self.exam and self.exam.result_date:
            date_str = self.exam.result_date.strftime('%Y/%m/%d')
            suffix = ' BS' if self.exam.result_date_is_bs else ' AD'
            display_date = f"{date_str}{suffix}"
        else:
            display_date = date.today().strftime('%Y/%m/%d')
            
        date_para = Paragraph(f"DATE OF ISSUE: &nbsp;&nbsp;&nbsp;{display_date}", ParagraphStyle('Date', fontSize=9, fontName='Times-Bold', leftIndent=1))
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
        """
        Build and return the PDF document as a bytes object.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.8*cm,
            leftMargin=0.8*cm,
            topMargin=0.4*cm,
            bottomMargin=0.4*cm,
            title=f"Marksheet - {self.student.name}",
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
    """
    Generates an NEB 11 merged PDF marksheet for all students in a class.
    Combines the output of NEB11MarksheetPDFGenerator for multiple students into one document.
    """

    def __init__(self, school, exam, cls_obj, student_results, student_mark_map, base_font_size=22.0, line_spacing=1.0, exam_title=""):
        """
        Initialize the Class NEB11 Marksheets generator.
        """
        self.school = school
        self.exam = exam
        self.cls_obj = cls_obj
        self.student_results = student_results
        self.student_mark_map = student_mark_map
        self.base_font_size = base_font_size
        self.line_spacing = line_spacing
        self.exam_title = exam_title

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
            title=f"Marksheets - {self.cls_obj.name}",
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
            
            # Delegate to individual marksheet generator
            single_gen = NEB11MarksheetPDFGenerator(
                self.school, self.exam, student, sr, mark_entries,
                base_font_size=self.base_font_size, line_spacing=self.line_spacing,
                exam_title=self.exam_title
            )
            
            # Wrap the entire marksheet inside a KeepTogether to prevent page breaks in the middle
            student_story = single_gen.get_story()
            story.append(KeepTogether(student_story))
            
            if idx < len(self.student_results) - 1:
                story.append(PageBreak())

        doc.build(story, onFirstPage=add_border, onLaterPages=add_border)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
