"""
Base utilities and imports for PDF Generators using ReportLab
"""
import io
import os
from decimal import Decimal

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
    HRFlowable, Image, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def format_mark(val):
    """
    Format a numeric mark to string, removing trailing decimal zeros if it's an integer.
    Returns '—' if the value is None.
    """
    if val is None:
        return '—'
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
    """
    Safely retrieve the school logo as a ReportLab Image object.
    Checks if the logo exists on the filesystem before attempting to load it.
    Returns None if there's no logo or if an error occurs.
    """
    try:
        if school.logo and os.path.exists(school.logo.path):
            return Image(school.logo.path, width=width, height=height, kind='proportional')
    except Exception:
        pass
    return None
