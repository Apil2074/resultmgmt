"""
Patch script: add password-reset feature to the schools app.
Run from the backend directory:  python .patch_reset.py
"""
import pathlib

ROOT = pathlib.Path(__file__).parent

# ────────────────────────────────────────────────────────────────
# 1.  urls_web_schools.py
# ────────────────────────────────────────────────────────────────
urls_path = ROOT / 'apps' / 'schools' / 'urls_web_schools.py'
urls_path.write_text(
    "from django.urls import path\n"
    "from .views_web import (\n"
    "    school_profile, session_list, super_schools,\n"
    "    create_school_and_admin, subscription_expired,\n"
    "    edit_school, reset_school_admin_password,\n"
    ")\n"
    "\n"
    "urlpatterns = [\n"
    "    path('profile/', school_profile, name='school_profile'),\n"
    "    path('sessions/', session_list, name='session_list'),\n"
    "    path('', super_schools, name='super_schools'),\n"
    "    path('create/', create_school_and_admin, name='create_school_and_admin'),\n"
    "    path('edit/<int:school_id>/', edit_school, name='edit_school'),\n"
    "    path('reset-password/<int:school_id>/', reset_school_admin_password, name='reset_school_admin_password'),\n"
    "    path('subscription-expired/', subscription_expired, name='subscription_expired'),\n"
    "]\n",
    encoding='utf-8',
)
print('[1] urls_web_schools.py written OK')


# ────────────────────────────────────────────────────────────────
# 2.  super_schools_list.html — add "Reset Password" button
# ────────────────────────────────────────────────────────────────
list_path = ROOT / 'templates' / 'schools' / 'super_schools_list.html'
list_text = list_path.read_text(encoding='utf-8')

OLD_BTN = (
    "              <a href=\"{% url 'edit_school' s.id %}\" "
    "class=\"btn btn-sm btn-outline-primary\" title=\"Edit School Details\">\n"
    "                <i class=\"bi bi-pencil-fill me-1\"></i>Edit\n"
    "              </a>"
)
NEW_BTN = (
    "              <a href=\"{% url 'edit_school' s.id %}\" "
    "class=\"btn btn-sm btn-outline-primary\" title=\"Edit School Details\">\n"
    "                <i class=\"bi bi-pencil-fill me-1\"></i>Edit\n"
    "              </a>\n"
    "              <a href=\"{% url 'reset_school_admin_password' s.id %}\" "
    "class=\"btn btn-sm btn-outline-danger\" title=\"Reset Admin Password\">\n"
    "                <i class=\"bi bi-shield-lock-fill me-1\"></i>Reset Password\n"
    "              </a>"
)

if OLD_BTN in list_text:
    list_path.write_text(list_text.replace(OLD_BTN, NEW_BTN, 1), encoding='utf-8')
    print('[2] super_schools_list.html updated OK')
else:
    print('[2] WARNING: edit button anchor not found — check indentation')
    # Show what the file has around that area
    idx = list_text.find("edit_school")
    print('Context:', repr(list_text[max(0,idx-10):idx+150]))


# ────────────────────────────────────────────────────────────────
# 3.  reset_admin_password.html (new template)
# ────────────────────────────────────────────────────────────────
tmpl_path = ROOT / 'templates' / 'schools' / 'reset_admin_password.html'
tmpl_path.write_text(
    r"""{% extends 'base.html' %}
{% block title %}Reset Admin Password — {{ school.name }}{% endblock %}
{% block page_title %}Reset Admin Password{% endblock %}

{% block extra_css %}
<style>
.reset-card { max-width: 540px; margin: 0 auto; }
.password-toggle { cursor: pointer; border-left: 1px solid #cbd5e1; }
.strength-bar { height: 4px; border-radius: 2px; transition: width .3s, background .3s; width: 0%; }
</style>
{% endblock %}

{% block content %}
<div class="page-header mb-4">
  <div>
    <h1 class="page-title">🔐 Reset Admin Password</h1>
    <div class="page-subtitle">
      School: <strong>{{ school.name }}</strong> &nbsp;|&nbsp;
      Admin: <strong>{{ admin_user.get_full_name|default:admin_user.username }}</strong>
      <span class="text-muted">({{ admin_user.username }})</span>
    </div>
  </div>
  <a href="{% url 'super_schools' %}" class="btn btn-outline-secondary">
    <i class="bi bi-arrow-left me-1"></i> Back to Schools
  </a>
</div>

<div class="reset-card card shadow-sm">
  <div class="card-header bg-white py-3 border-bottom">
    <h5 class="card-title mb-0 fw-semibold">
      <i class="bi bi-shield-lock-fill text-warning me-2"></i>
      Set a New Password for <em>{{ admin_user.username }}</em>
    </h5>
  </div>

  <div class="card-body p-4">

    <div class="alert alert-warning d-flex align-items-start gap-2 mb-4" role="alert">
      <i class="bi bi-exclamation-triangle-fill fs-5 mt-1 flex-shrink-0"></i>
      <div>
        <strong>Caution:</strong> The admin will be logged out from all active sessions
        once the password is changed. Communicate the new password securely.
      </div>
    </div>

    <form method="POST" id="resetForm" novalidate>
      {% csrf_token %}

      <!-- Read-only admin info -->
      <div class="mb-3">
        <label class="form-label fw-medium">School Admin Account</label>
        <div class="input-group">
          <span class="input-group-text"><i class="bi bi-person-fill"></i></span>
          <input type="text" class="form-control bg-light" value="{{ admin_user.username }}" readonly>
        </div>
        <div class="form-text text-muted">
          {{ admin_user.email|default:"No email set" }}
          &nbsp;|&nbsp; Joined {{ admin_user.date_joined|date:"Y-m-d" }}
        </div>
      </div>

      <!-- New Password -->
      <div class="mb-3">
        <label for="new_password" class="form-label fw-medium">
          New Password <span class="text-danger">*</span>
        </label>
        <div class="input-group">
          <span class="input-group-text"><i class="bi bi-lock-fill"></i></span>
          <input type="password" id="new_password" name="new_password"
                 class="form-control" placeholder="Minimum 8 characters"
                 autocomplete="new-password" required>
          <button type="button" class="btn btn-outline-secondary password-toggle"
                  onclick="togglePwd('new_password', this)" title="Show / hide">
            <i class="bi bi-eye-fill"></i>
          </button>
        </div>
        <div class="mt-2">
          <div class="bg-light rounded" style="height:4px;">
            <div class="strength-bar rounded" id="strengthBar"></div>
          </div>
          <small id="strengthLabel" class="text-muted"></small>
        </div>
      </div>

      <!-- Confirm Password -->
      <div class="mb-4">
        <label for="confirm_password" class="form-label fw-medium">
          Confirm New Password <span class="text-danger">*</span>
        </label>
        <div class="input-group">
          <span class="input-group-text"><i class="bi bi-lock-fill"></i></span>
          <input type="password" id="confirm_password" name="confirm_password"
                 class="form-control" placeholder="Repeat the password"
                 autocomplete="new-password" required>
          <button type="button" class="btn btn-outline-secondary password-toggle"
                  onclick="togglePwd('confirm_password', this)" title="Show / hide">
            <i class="bi bi-eye-fill"></i>
          </button>
        </div>
        <div id="matchMsg" class="form-text mt-1"></div>
      </div>

      <div class="d-flex gap-2">
        <button type="submit" class="btn btn-danger" id="submitBtn">
          <i class="bi bi-shield-lock-fill me-1"></i> Reset Password
        </button>
        <a href="{% url 'super_schools' %}" class="btn btn-outline-secondary">Cancel</a>
      </div>
    </form>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
function togglePwd(id, btn) {
  var inp = document.getElementById(id);
  var ico = btn.querySelector('i');
  if (inp.type === 'password') {
    inp.type = 'text';
    ico.classList.replace('bi-eye-fill', 'bi-eye-slash-fill');
  } else {
    inp.type = 'password';
    ico.classList.replace('bi-eye-slash-fill', 'bi-eye-fill');
  }
}

document.getElementById('new_password').addEventListener('input', function () {
  var pw = this.value;
  var bar = document.getElementById('strengthBar');
  var lbl = document.getElementById('strengthLabel');
  var score = 0;
  if (pw.length >= 8)        score++;
  if (/[A-Z]/.test(pw))     score++;
  if (/[0-9]/.test(pw))     score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  var colors = ['#ef4444','#f97316','#eab308','#22c55e'];
  var widths = ['25%','50%','75%','100%'];
  var labels = ['Weak','Fair','Good','Strong'];
  if (!pw) { bar.style.width='0%'; lbl.textContent=''; return; }
  var i = score - 1;
  bar.style.width = widths[i] || '25%';
  bar.style.background = colors[i] || '#ef4444';
  lbl.textContent = labels[i] || 'Weak';
  lbl.style.color = colors[i] || '#ef4444';
  checkMatch();
});

document.getElementById('confirm_password').addEventListener('input', checkMatch);

function checkMatch() {
  var pw  = document.getElementById('new_password').value;
  var cpw = document.getElementById('confirm_password').value;
  var msg = document.getElementById('matchMsg');
  if (!cpw) { msg.textContent = ''; return; }
  if (pw === cpw) {
    msg.textContent = '✔ Passwords match';
    msg.style.color = '#22c55e';
  } else {
    msg.textContent = '✘ Passwords do not match';
    msg.style.color = '#ef4444';
  }
}

document.getElementById('resetForm').addEventListener('submit', function (e) {
  var pw  = document.getElementById('new_password').value;
  var cpw = document.getElementById('confirm_password').value;
  if (pw.length < 8) {
    e.preventDefault();
    alert('Password must be at least 8 characters.');
    return;
  }
  if (pw !== cpw) {
    e.preventDefault();
    alert('Passwords do not match.');
    return;
  }
  var btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Resetting…';
});
</script>
{% endblock %}
""",
    encoding='utf-8',
)
print('[3] reset_admin_password.html written OK')

print('\nAll done.')
