"""
Shared HTML email utility for E-Natija.
All app-wide emails should use build_html_email() for a consistent look.
"""
from django.utils.html import strip_tags


_BRAND_COLOR = "#4f46e5"
_BRAND_DARK  = "#3730a3"


def _base_template(header_html: str, body_html: str, footer_text: str = "\u00a9 E-Natija. All rights reserved.") -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="100%" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);border:1px solid #e2e8f0;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,{_BRAND_COLOR} 0%,{_BRAND_DARK} 100%);padding:32px 24px;text-align:center;">
              {header_html}
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 32px;color:#374151;">
              {body_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;padding:20px 32px;text-align:center;border-top:1px solid #f1f5f9;color:#94a3b8;font-size:13px;">
              {footer_text}
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _logo_header(subtitle: str = "Result Management Software") -> str:
    return f"""
      <h1 style="color:white;margin:0;font-size:28px;letter-spacing:1px;font-weight:700;">E-Natija</h1>
      <p style="color:#e0e7ff;margin:8px 0 0 0;font-size:14px;font-weight:500;">{subtitle}</p>
    """


def _cta_button(url: str, label: str) -> str:
    return f"""
      <div style="text-align:center;margin:32px 0;">
        <a href="{url}"
           style="background-color:{_BRAND_COLOR};color:white;padding:14px 32px;
                  text-decoration:none;border-radius:6px;font-weight:600;
                  font-size:16px;display:inline-block;
                  box-shadow:0 4px 14px rgba(79,70,229,0.35);">
          {label}
        </a>
      </div>
    """


def _info_row(label: str, value: str) -> str:
    return f"""
      <tr>
        <td style="padding:8px 0;color:#6b7280;font-size:14px;width:40%;">{label}</td>
        <td style="padding:8px 0;color:#111827;font-weight:600;font-size:14px;">{value}</td>
      </tr>
    """


# ──────────────────────────────────────────────────────────────────────────────
# Public builders
# ──────────────────────────────────────────────────────────────────────────────

def password_reset_email(name: str, reset_link: str) -> tuple[str, str, str]:
    """Returns (subject, plain_text, html)"""
    subject = "Reset Your Password \u2014 E-Natija"
    body = f"""
      <h2 style="margin-top:0;color:#1e293b;font-size:22px;">Hello {name},</h2>
      <p style="color:#4b5563;line-height:1.7;font-size:16px;">
        We received a request to reset the password for your account on <strong>E-Natija</strong>.
      </p>
      <p style="color:#4b5563;line-height:1.7;font-size:16px;">
        Click the button below to choose a new password:
      </p>
      {_cta_button(reset_link, "Reset My Password")}
      <p style="color:#6b7280;font-size:13px;line-height:1.6;border-top:1px solid #f1f5f9;padding-top:16px;margin-bottom:0;">
        <em>This link is valid for a limited time and can only be used once.</em><br>
        If you did not request a password reset, you can safely ignore this email.
      </p>
    """
    html = _base_template(_logo_header(), body)
    return subject, strip_tags(html), html


def teacher_password_reset_email(name: str, reset_link: str) -> tuple[str, str, str]:
    """Returns (subject, plain_text, html)"""
    subject = "Set Your E-Natija Password"
    body = f"""
      <h2 style="margin-top:0;color:#1e293b;font-size:22px;">Hello {name},</h2>
      <p style="color:#4b5563;line-height:1.7;font-size:16px;">
        Your school admin has requested a password reset for your <strong>E-Natija</strong> teacher account.
      </p>
      <p style="color:#4b5563;line-height:1.7;font-size:16px;">
        Click the button below to set your new password and access the system:
      </p>
      {_cta_button(reset_link, "Set My Password")}
      <p style="color:#6b7280;font-size:13px;line-height:1.6;border-top:1px solid #f1f5f9;padding-top:16px;margin-bottom:0;">
        <em>This link is valid for a limited time and can only be used once.</em><br>
        If you were not expecting this email, please contact your school admin.
      </p>
    """
    html = _base_template(_logo_header(), body)
    return subject, strip_tags(html), html


def demo_activation_email(name: str, activation_link: str) -> tuple[str, str, str]:
    """Returns (subject, plain_text, html)"""
    subject = "Activate Your E-Natija Demo Account"
    body = f"""
      <h2 style="margin-top:0;color:#1e293b;font-size:22px;">Welcome, {name}! &#x1F389;</h2>
      <p style="color:#4b5563;line-height:1.7;font-size:16px;">
        Thank you for applying for a demo on <strong>E-Natija</strong>.
        Your account has been created and is just one click away from being active.
      </p>
      {_cta_button(activation_link, "Activate My Account")}
      <p style="color:#6b7280;font-size:13px;line-height:1.6;border-top:1px solid #f1f5f9;padding-top:16px;margin-bottom:0;">
        This activation link is valid for a limited time.<br>
        If you did not apply for a demo, you can safely ignore this email.
      </p>
    """
    html = _base_template(_logo_header("Try E-Natija for Free"), body)
    return subject, strip_tags(html), html


def superadmin_new_demo_email(school_name: str, admin_name: str, admin_email: str, admin_phone: str) -> tuple[str, str, str]:
    """Returns (subject, plain_text, html)"""
    subject = "[ALERT] New Demo Tenant Registered - E-Natija"
    rows = (
        _info_row("School", school_name)
        + _info_row("Admin Name", admin_name)
        + _info_row("Email", admin_email)
        + _info_row("Phone", admin_phone)
    )
    body = f"""
      <h2 style="margin-top:0;color:#1e293b;font-size:22px;">&#x1F3EB; New Demo Registration</h2>
      <p style="color:#4b5563;line-height:1.7;font-size:16px;">
        A new school has applied for a demo account on <strong>E-Natija</strong>.
        Here are their details:
      </p>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f8fafc;border-radius:8px;padding:16px 20px;margin:20px 0;border:1px solid #e2e8f0;">
        {rows}
      </table>
      <p style="color:#6b7280;font-size:13px;line-height:1.6;">
        The user has been sent an activation email. Their account will be active once they click the link.
      </p>
    """
    html = _base_template(_logo_header("Admin Notification"), body)
    return subject, strip_tags(html), html


def school_welcome_email(school_name: str, username: str, password: str, dashboard_url: str) -> tuple[str, str, str]:
    """Returns (subject, plain_text, html)"""
    subject = f"Welcome to E-Natija - {school_name}"
    rows = _info_row("Username", username) + _info_row("Password", password)
    body = f"""
      <h2 style="margin-top:0;color:#1e293b;font-size:22px;">Welcome to E-Natija! &#x1F680;</h2>
      <p style="color:#4b5563;line-height:1.7;font-size:16px;">
        We are thrilled to have <strong>{school_name}</strong> on board.
        Your school admin account has been created with the credentials below.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f8fafc;border-radius:8px;padding:16px 20px;margin:20px 0;border:1px solid #e2e8f0;">
        {rows}
      </table>
      <p style="color:#ef4444;font-size:13px;font-weight:600;margin-top:0;">
        &#x26A0; Please change your password after your first login.
      </p>
      {_cta_button(dashboard_url, "Go to Dashboard")}
      <p style="color:#6b7280;font-size:13px;line-height:1.6;border-top:1px solid #f1f5f9;padding-top:16px;margin-bottom:0;">
        Get started by setting up your academic sessions, classes, and adding your teachers.
      </p>
    """
    html = _base_template(_logo_header(), body)
    return subject, strip_tags(html), html
