import re

with open('frontend/login.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace CSS
css_old = r'<style>[\s\S]*?</style>'
css_new = r'''<style>
    .split-layout {
      display: flex;
      min-height: calc(100vh - 77px);
      background: var(--ns-soft);
    }
    .split-left {
      flex: 1.2;
      background: linear-gradient(140deg, #0e2c4e, #174f85);
      color: white;
      padding: 60px 80px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      overflow: hidden;
    }
    .split-left::after {
      content: "";
      position: absolute;
      top: -10%; left: -10%; width: 50%; height: 50%;
      background: radial-gradient(circle, rgba(23,105,224,0.15) 0%, transparent 70%);
      z-index: 0;
    }
    .left-content { position: relative; z-index: 1; }
    
    .left-logo {
      font-family: Poppins, sans-serif;
      font-size: 2.2rem;
      font-weight: 800;
      letter-spacing: -0.7px;
      margin-bottom: 60px;
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
    }
    .left-logo .logo-icon { color: #65dbc4; }
    .left-logo .logo-text { color: white; }
    .left-logo .logo-text span { color: #65dbc4; }
    
    .left-title {
      font-family: Poppins, sans-serif;
      font-size: 3.5rem;
      line-height: 1.15;
      margin-bottom: 24px;
      letter-spacing: -1px;
    }
    .left-title span { color: #65dbc4; }
    
    .left-desc {
      font-size: 1.15rem;
      line-height: 1.7;
      color: #d7e6f5;
      max-width: 500px;
      margin-bottom: 60px;
    }
    
    .left-features {
      display: flex;
      gap: 35px;
      margin-bottom: 60px;
    }
    .feature-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      gap: 12px;
      font-weight: 700;
      font-size: 0.9rem;
      color: #edf7ff;
    }
    .feature-item i {
      font-size: 1.8rem;
      color: #65dbc4;
    }
    
    .left-quote {
      border-left: 4px solid #65dbc4;
      padding-left: 18px;
      font-size: 1.1rem;
      font-weight: 600;
      color: #d7e6f5;
    }

    .split-right {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 40px;
      background: var(--ns-soft);
    }
    
    .login-card {
      background: white;
      border-radius: 20px;
      padding: 45px 40px;
      width: 100%;
      max-width: 520px;
      box-shadow: 0 10px 40px rgba(16, 36, 62, 0.08);
    }
    
    .card-title {
      font-family: Poppins, sans-serif;
      font-size: 1.8rem;
      text-align: center;
      margin-bottom: 5px;
      font-weight: 800;
    }
    .card-title span { color: var(--ns-blue); }
    .card-sub {
      text-align: center;
      color: var(--ns-muted);
      margin-bottom: 25px;
      font-size: 0.95rem;
    }
    
    .role-grid-title {
      font-weight: 800;
      margin-bottom: 12px;
      font-size: 1rem;
      color: var(--ns-ink);
    }
    .role-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 12px;
    }
    .role-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 15px 5px;
      border: 1px solid var(--ns-line);
      border-radius: 12px;
      background: white;
      cursor: pointer;
      transition: all 0.2s;
      color: var(--ns-ink);
      font-weight: 700;
      font-size: 0.85rem;
      position: relative;
      font-family: inherit;
    }
    .role-btn i { font-size: 1.4rem; color: var(--ns-muted); transition: color 0.2s; }
    
    .role-btn:nth-child(1) i { color: var(--ns-blue); }
    .role-btn:nth-child(2) i { color: #087d60; }
    .role-btn:nth-child(3) i { color: #7045b5; }
    .role-btn:nth-child(4) i { color: #d97706; }
    .role-btn:nth-child(5) i { color: var(--ns-teal); }
    .role-btn:nth-child(6) i { color: #e11d48; }

    .role-btn.active {
      border-color: var(--ns-blue);
      background: #f4f8fc;
      box-shadow: 0 4px 12px rgba(23, 105, 224, 0.1);
    }
    .role-btn.active::after {
      content: '\f058';
      font-family: 'Font Awesome 6 Free';
      font-weight: 900;
      position: absolute;
      top: -6px;
      right: -6px;
      color: var(--ns-blue);
      background: white;
      border-radius: 50%;
      font-size: 1.2rem;
    }
    
    .pill-toggle {
      display: flex;
      background: #f1f5f9;
      border-radius: 999px;
      padding: 6px;
      margin-bottom: 8px;
    }
    .pill-btn {
      flex: 1;
      padding: 12px;
      border: none;
      background: transparent;
      border-radius: 999px;
      font-weight: 700;
      color: var(--ns-muted);
      cursor: pointer;
      transition: all 0.2s;
      font-family: inherit;
      font-size: 0.95rem;
    }
    .pill-btn.active {
      background: var(--ns-blue);
      color: white;
      box-shadow: 0 4px 10px rgba(23, 105, 224, 0.25);
    }
    .switch-hint {
      text-align: center;
      font-size: 0.85rem;
      color: var(--ns-muted);
      margin-bottom: 25px;
    }
    
    .form-group label {
      font-weight: 700;
      font-size: 0.9rem;
      margin-bottom: 8px;
      display: block;
      color: var(--ns-ink);
    }
    
    .input-with-icon {
      position: relative;
      margin-bottom: 20px;
    }
    .input-with-icon i.icon-left {
      position: absolute;
      left: 16px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--ns-muted);
      font-size: 1.1rem;
    }
    .input-with-icon input, .input-with-icon select {
      width: 100%;
      padding: 14px 16px 14px 45px;
      border: 1px solid var(--ns-line);
      border-radius: 12px;
      font-size: 0.95rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s;
      box-sizing: border-box;
    }
    .input-with-icon input:focus, .input-with-icon select:focus {
      border-color: var(--ns-blue);
    }
    .input-with-icon i.icon-right {
      position: absolute;
      right: 16px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--ns-muted);
      cursor: pointer;
    }
    
    .forgot-link-right {
      display: block;
      text-align: right;
      font-size: 0.85rem;
      color: var(--ns-blue);
      font-weight: 700;
      text-decoration: none;
      margin-top: -10px;
      margin-bottom: 25px;
      cursor: pointer;
    }
    .forgot-link-right:hover { text-decoration: underline; }
    
    .btn-login-main {
      width: 100%;
      padding: 14px;
      border-radius: 12px;
      background: var(--ns-blue);
      color: white;
      font-weight: 800;
      font-size: 1rem;
      border: none;
      cursor: pointer;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      box-shadow: 0 8px 20px rgba(23, 105, 224, 0.25);
      transition: transform 0.2s;
      font-family: inherit;
    }
    .btn-login-main:hover {
      transform: translateY(-2px);
    }
    
    .bottom-links {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 15px;
      margin-top: 25px;
      font-size: 0.85rem;
    }
    .bottom-links a {
      color: var(--ns-blue);
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
    }
    .bottom-links a:hover { text-decoration: underline; }
    .bottom-links span { color: var(--ns-line); }
    
    .form-panel { display: none; }
    .form-panel.active { display: block; }
    .error-msg, .success-msg {
      padding: 12px 16px;
      border-radius: 12px;
      margin-bottom: 16px;
      font-size: 0.9rem;
      display: none;
    }
    .error-msg { background: #fee2e2; color: #dc2626; }
    .success-msg { background: #d1fae5; color: #059669; }
    
    @media (max-width: 900px) {
      .split-layout { flex-direction: column; }
      .split-left { padding: 40px 20px; }
      .left-title { font-size: 2.5rem; }
      .left-features { flex-wrap: wrap; gap: 15px; }
      .feature-item { width: 45%; }
    }
    @media (max-width: 500px) {
      .role-grid { grid-template-columns: repeat(2, 1fr); }
    }
</style>'''
content = re.sub(css_old, css_new, content, count=1)

# 2. Replace HTML wrapper
html_old = r'<div class="login-wrapper">.*?</div>\s*</div>'
html_new = '''<div class="split-layout">
    <div class="split-left">
      <div class="left-content">
        <a href="index.html" class="left-logo">
          <span class="logo-icon">📸</span>
          <span class="logo-text">Nagrik<span>Snap</span></span>
        </a>
        
        <h1 class="left-title">Connecting People for a<br><span>Better Tomorrow</span></h1>
        <p class="left-desc">A unified platform to bridge citizens, government, universities, industries and administrators for real societal impact.</p>
        
        <div class="left-features">
          <div class="feature-item"><i class="far fa-lightbulb"></i><span>Real<br>Problems</span></div>
          <div class="feature-item"><i class="fas fa-users"></i><span>Collaborative<br>Solutions</span></div>
          <div class="feature-item"><i class="fas fa-cogs"></i><span>Multi-Stakeholder<br>Engagement</span></div>
          <div class="feature-item"><i class="fas fa-chart-line"></i><span>Measurable<br>Impact</span></div>
        </div>
        
        <div class="left-quote">
          "Together for a Stronger, Smarter and More Inclusive Society"
        </div>
      </div>
    </div>
    
    <div class="split-right">
      <div class="login-card">
        <h2 class="card-title" id="cardTitle">Welcome to <span>NagrikSnap</span></h2>
        <p class="card-sub" id="cardSub">Sign in to your workspace</p>

        <div class="role-grid-title">Select Your Role</div>
        <div class="role-grid" role="group" aria-label="Choose your workspace">
          <button type="button" class="role-btn active" id="tabCitizen" onclick="setRole('citizen')"><i class="fas fa-users"></i><span>Citizen</span></button>
          <button type="button" class="role-btn" id="tabGovernment" onclick="setRole('govt_admin')"><i class="fas fa-landmark"></i><span>Government</span></button>
          <button type="button" class="role-btn" id="tabUniversity" onclick="setRole('university')"><i class="fas fa-graduation-cap"></i><span>University</span></button>
          <button type="button" class="role-btn" id="tabIndustry" onclick="setRole('industry')"><i class="fas fa-industry"></i><span>Industry</span></button>
          <button type="button" class="role-btn" id="tabAdmin" onclick="setRole('admin')"><i class="fas fa-user-shield"></i><span>Nodal Admin</span></button>
          <button type="button" class="role-btn" id="tabSuperAdmin" onclick="setRole('super_admin')"><i class="fas fa-cog"></i><span>Super Admin</span></button>
        </div>
        
        <p class="hint" id="roleHint" style="text-align:center;margin-bottom:15px;">Sign in with your citizen account. Each account can access only its assigned workspace.</p>

        <div class="pill-toggle" id="modePills">
          <button type="button" class="pill-btn active" id="pillLogin" onclick="setMode('login')">Sign In</button>
          <button type="button" class="pill-btn" id="pillSignup" onclick="setMode('signup')">Sign Up</button>
        </div>
        <p class="switch-hint swipe-hint">Switch between Sign In and Sign Up</p>

        <div class="error-msg" id="errorMsg"></div>
        <div class="success-msg" id="successMsg"></div>

        <!-- ========== LOGIN ========== -->
        <div class="form-panel active" id="panelLogin">
          <form onsubmit="doLogin(event)">
            <div class="form-group">
              <label>Name / Username</label>
              <div class="input-with-icon">
                <i class="far fa-user icon-left"></i>
                <input type="text" id="loginName" placeholder="Your name or username" required />
              </div>
            </div>
            <div class="form-group">
              <label>Password</label>
              <div class="input-with-icon">
                <i class="fas fa-lock icon-left"></i>
                <input type="password" id="loginPass" placeholder="Password" required />
                <i class="far fa-eye-slash icon-right" onclick="const p=document.getElementById('loginPass'); if(p.type==='password'){p.type='text';this.className='far fa-eye icon-right';}else{p.type='password';this.className='far fa-eye-slash icon-right';}"></i>
              </div>
            </div>
            <a class="forgot-link-right" onclick="setMode('forgot')">Forgot password?</a>
            <button type="submit" class="btn-login-main">
               Login <i class="fas fa-arrow-right-to-bracket"></i>
            </button>
          </form>
          <button type="button" class="btn-login-main" id="demoLoginButton" onclick="doDemoLogin()" style="display:none;margin-top:12px;background:white;color:var(--ns-ink);border:1px solid var(--ns-line);">
            <i class="fas fa-bolt" style="color:var(--ns-blue)"></i> One-click demo sign-in
          </button>
          
          <div class="bottom-links" id="loginBottomLinks">
            <a id="signupLink" onclick="setMode('signup')">Create account (Sign up)</a>
            <span id="signupPipe">|</span>
            <a onclick="setMode('forgot')">Forgot password?</a>
          </div>
        </div>

        <!-- ========== SIGN UP ========== -->
        <div class="form-panel" id="panelSignup">
          <form onsubmit="doSignup(event)">
            <div class="form-group">
              <label>Full Name</label>
              <div class="input-with-icon">
                <i class="far fa-user icon-left"></i>
                <input type="text" id="suName" placeholder="Your full name" required />
              </div>
            </div>
            <div class="form-group">
              <label>Email Address</label>
              <div class="input-with-icon">
                <i class="far fa-envelope icon-left"></i>
                <input type="email" id="suEmail" placeholder="you@example.com" autocomplete="email" required />
              </div>
            </div>
            <div class="form-group">
              <label>Phone Number</label>
              <div class="input-with-icon">
                <i class="fas fa-phone icon-left"></i>
                <input type="tel" id="suPhone" placeholder="10-digit mobile" pattern="[0-9]{10}" required />
              </div>
            </div>
            <div class="form-group" id="suDeptGroup" style="display:none;">
              <label>Department</label>
              <div class="input-with-icon">
                <i class="fas fa-building icon-left"></i>
                <select id="suDept" class="dept-select">
                  <option value="Public Works / Roads">Public Works / Roads</option>
                  <option value="Sanitation / Waste Management">Sanitation / Waste</option>
                  <option value="Water Supply">Water Supply</option>
                  <option value="Electrical / Street Lights">Electrical / Street Lights</option>
                  <option value="Drainage / Sewerage">Drainage / Sewerage</option>
                  <option value="Parks & Horticulture">Parks & Horticulture</option>
                  <option value="General Administration">General Administration</option>
                </select>
              </div>
            </div>
            <div class="form-group">
              <label>Your Location (for nearby assignment)</label>
              <div class="input-with-icon">
                <i class="fas fa-location-dot icon-left"></i>
                <input type="text" id="suAddress" placeholder="Area / landmark / address" style="padding-right:110px;" />
                <button type="button" id="suLocBtn" title="Use GPS" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);padding:6px 12px;border-radius:8px;border:none;background:var(--ns-soft);cursor:pointer;font-weight:700;font-size:0.8rem;color:var(--ns-ink);"><i class="fas fa-location-crosshairs"></i> GPS</button>
              </div>
              <div id="suLocStatus" style="font-size:0.8rem;color:var(--ns-muted);margin-top:-10px;margin-bottom:15px;padding-left:5px;">Optional for citizens, recommended for admins</div>
              <input type="hidden" id="suLat" />
              <input type="hidden" id="suLng" />
            </div>
            
            <div class="form-group">
              <label>Create Password</label>
              <div class="input-with-icon">
                <i class="fas fa-lock icon-left"></i>
                <input type="password" id="suPass" placeholder="At least 10 characters" minlength="10" required />
              </div>
            </div>
            <div class="form-group">
              <label>Confirm Password</label>
              <div class="input-with-icon">
                <i class="fas fa-lock icon-left"></i>
                <input type="password" id="suPass2" placeholder="Re-enter password" minlength="6" required />
              </div>
            </div>
            <button type="submit" class="btn-login-main">
              <i class="fas fa-user-plus"></i> Sign Up
            </button>
          </form>
          <div class="bottom-links">
            <a onclick="setMode('login')">Already have account? Login</a>
          </div>
        </div>

        <!-- ========== FOR উভয়ের PASSWORD ========== -->
        <div class="form-panel" id="panelForgot">
          <div id="forgotStep1">
            <form onsubmit="sendOtp(event)">
              <div class="form-group">
                <label>Registered Email Address</label>
                <div class="input-with-icon">
                  <i class="far fa-envelope icon-left"></i>
                  <input type="email" id="fpEmail" placeholder="you@example.com" autocomplete="email" required />
                </div>
              </div>
              <button type="submit" class="btn-login-main">
                <i class="fas fa-sms"></i> Send OTP
              </button>
            </form>
          </div>
          <div id="forgotStep2" style="display:none;">
            <form onsubmit="resetPassword(event)">
              <div class="form-group">
                <label>Enter OTP</label>
                <div class="input-with-icon">
                  <i class="fas fa-key icon-left"></i>
                  <input type="text" id="fpOtp" placeholder="6-digit OTP" maxlength="6" required />
                </div>
              </div>
              <div class="form-group">
                <label>New Password</label>
                <div class="input-with-icon">
                  <i class="fas fa-lock icon-left"></i>
                  <input type="password" id="fpNewPass" placeholder="At least 10 characters" minlength="10" required />
                </div>
              </div>
              <div class="form-group">
                <label>Confirm New Password</label>
                <div class="input-with-icon">
                  <i class="fas fa-lock icon-left"></i>
                  <input type="password" id="fpNewPass2" placeholder="Re-enter password" minlength="6" required />
                </div>
              </div>
              <button type="submit" class="btn-login-main">
                <i class="fas fa-key"></i> Reset Password
              </button>
            </form>
          </div>
          <div class="bottom-links">
            <a onclick="setMode('login')">Back to Login</a>
          </div>
        </div>
      </div>
    </div>
</div>'''

content = re.sub(html_old, html_new, content, flags=re.DOTALL)

# 3. Update JavaScript variables
js_old_labels = r"const roleLabels = {.*?};"
js_new_labels = "const roleLabels = {citizen:'Citizen', govt_admin:'Government', university:'University', industry:'Industry', admin:'Nodal Admin', super_admin:'Super Admin'};"
content = re.sub(js_old_labels, js_new_labels, content)

js_old_tabs = r"const roleTabs = {.*?};"
js_new_tabs = "const roleTabs = {citizen:'tabCitizen', govt_admin:'tabGovernment', university:'tabUniversity', industry:'tabIndustry', admin:'tabAdmin', super_admin:'tabSuperAdmin'};"
content = re.sub(js_old_tabs, js_new_tabs, content)

js_old_hide_signup = r"document.getElementById\('signupLink'\).style.display = citizenRole \? '' : 'none';"
js_new_hide_signup = r"document.getElementById('signupLink').style.display = citizenRole ? '' : 'none';\n      const sp = document.getElementById('signupPipe'); if (sp) sp.style.display = citizenRole ? '' : 'none';"
content = re.sub(js_old_hide_signup, js_new_hide_signup, content)

with open('frontend/login.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done!")
