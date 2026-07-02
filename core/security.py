"""
Core Security Utilities
-----------------------
Reusable helpers for:
  - Image / Excel upload validation
  - Trusted client IP extraction (proxy-aware)
  - Safe redirect URL validation
"""
import logging
import mimetypes
from urllib.parse import urlparse

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_IMAGE_MIMES = frozenset({'image/jpeg', 'image/png', 'image/gif', 'image/webp'})
ALLOWED_EXCEL_MIMES = frozenset({
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
})
MAX_IMAGE_SIZE = 200 * 1024   # 200 KB
MAX_EXCEL_SIZE = 20 * 1024 * 1024  # 20 MB


# ---------------------------------------------------------------------------
# MIME Detection
# ---------------------------------------------------------------------------

def _sniff_mime(file):
    """
    Read the file header to detect the real MIME type.
    Falls back to extension-based detection if python-magic is not installed.
    """
    file.seek(0)
    header = file.read(2048)
    file.seek(0)

    # Preferred: python-magic reads the actual file magic bytes
    try:
        import magic
        return magic.from_buffer(header, mime=True)
    except ImportError:
        pass

    # Fallback 1: ZIP signature → xlsx
    if header[:2] == b'PK':
        # Could be xlsx. Validate via openpyxl later.
        name = getattr(file, 'name', '')
        if name.endswith('.xls'):
            return 'application/vnd.ms-excel'
        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    # Fallback 2: imghdr for common image types
    import imghdr
    kind = imghdr.what(None, h=header)
    if kind:
        return f'image/{kind}'

    # Fallback 3: extension-based guess
    name = getattr(file, 'name', '')
    mime, _ = mimetypes.guess_type(name)
    return mime or 'application/octet-stream'


# ---------------------------------------------------------------------------
# Upload Validators
# ---------------------------------------------------------------------------

def validate_image_upload(file):
    """
    Validate that *file* is a safe image upload.
    Raises ``ValidationError`` if the file is invalid.
    Checks: size limit, MIME type, and Pillow header verification.
    """
    if file is None:
        return

    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            f"Image file too large. Maximum allowed size is 200 KB "
            f"(uploaded: {file.size // 1024:,} KB)."
        )

    mime = _sniff_mime(file)
    if mime not in ALLOWED_IMAGE_MIMES:
        raise ValidationError(
            f"Invalid file type detected ('{mime}'). "
            "Only JPEG, PNG, GIF and WebP images are allowed."
        )

    # Re-validate with Pillow — catches disguised non-images
    try:
        from PIL import Image
        file.seek(0)
        img = Image.open(file)
        img.verify()
        file.seek(0)
    except Exception:
        raise ValidationError("The uploaded file is not a valid image.")


def validate_excel_upload(file):
    """
    Validate that *file* is a safe Excel upload (.xlsx / .xls).
    Raises ``ValidationError`` if the file is invalid.
    """
    if file is None:
        return

    if file.size > MAX_EXCEL_SIZE:
        raise ValidationError(
            "Excel file is too large. Maximum allowed size is 20 MB."
        )

    mime = _sniff_mime(file)
    if mime not in ALLOWED_EXCEL_MIMES:
        raise ValidationError(
            f"Invalid file type detected ('{mime}'). "
            "Only Excel files (.xlsx, .xls) are accepted."
        )


# ---------------------------------------------------------------------------
# Trusted Client IP
# ---------------------------------------------------------------------------

def get_trusted_client_ip(request):
    """
    Extract the real client IP address.

    Only trusts ``X-Forwarded-For`` when ``TRUSTED_PROXY_IPS`` is configured
    in settings AND the direct sender (``REMOTE_ADDR``) is listed there.
    This prevents IP spoofing by arbitrary clients.
    """
    from django.conf import settings
    trusted_proxies = getattr(settings, 'TRUSTED_PROXY_IPS', [])

    remote_addr = request.META.get('REMOTE_ADDR', '')

    if trusted_proxies and remote_addr in trusted_proxies:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            # Leftmost entry is the original client IP
            ip = xff.split(',')[0].strip()
            if ip:
                return ip

    return remote_addr


# ---------------------------------------------------------------------------
# Safe Redirect
# ---------------------------------------------------------------------------

def safe_redirect_url(url, request):
    """
    Return *url* only if it is safe (relative path, same host).
    Returns ``None`` for external, protocol-relative, or empty URLs.

    Use this instead of directly redirecting to user-supplied ``next=`` params.
    """
    if not url:
        return None

    # Block protocol-relative URLs like //evil.com
    if url.startswith('//'):
        logger.warning(
            "Blocked protocol-relative redirect to '%s' (IP: %s)",
            url, get_trusted_client_ip(request),
        )
        return None

    parsed = urlparse(url)

    # Reject anything with a scheme (http, https, ftp, javascript…)
    if parsed.scheme:
        logger.warning(
            "Blocked external redirect to '%s' (IP: %s)",
            url, get_trusted_client_ip(request),
        )
        return None

    # Reject anything with an explicit host that differs from ours
    if parsed.netloc and parsed.netloc != request.get_host():
        logger.warning(
            "Blocked cross-host redirect to '%s' (IP: %s)",
            url, get_trusted_client_ip(request),
        )
        return None

    return url
