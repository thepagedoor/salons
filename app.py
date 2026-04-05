from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
import csv
import os
import re
from github_upload import upload_to_github

app = Flask(__name__)
DB = "leads.db"
CSV_FILE = "leads.csv"

# -------------------- DB SETUP --------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        address TEXT,
        category TEXT,
        area TEXT,
        status TEXT DEFAULT 'NEW',
        UNIQUE(phone)
    )
    """)
    conn.commit()
    conn.close()

# -------------------- CLEANING --------------------

def clean_text(value):
    if not value:
        return ""

    # Remove weird icons + non-ascii
    value = re.sub(r'[^\x00-\x7F]+', ' ', value)

    # Remove newlines
    value = value.replace("\n", " ")

    # Remove extra spaces
    value = re.sub(r'\s+', ' ', value)

    return value.strip()


def clean_phone(phone):
    if not phone:
        return ""

    # Step 1: basic clean
    phone = clean_text(phone)

    # Step 2: keep only digits
    phone = re.sub(r'\D', '', phone)

    # Step 3: remove leading zero (India)
    if phone.startswith("0"):
        phone = phone[1:]

    return phone

# -------------------- IMPORT CSV --------------------
def import_csv():
    if not os.path.exists(CSV_FILE):
        print("⚠️ leads.csv not found")
        return

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    inserted = 0
    duplicates = 0

    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                name = clean_text(row.get("Name"))
                phone = clean_phone(row.get("Phone"))
                address = clean_text(row.get("Address"))
                category = clean_text(row.get("Category"))
                area = clean_text(row.get("Area"))

                # 🚀 ONLY duplicate control
                c.execute("""
                INSERT OR IGNORE INTO leads (name, phone, address, category, area)
                VALUES (?, ?, ?, ?, ?)
                """, (name, phone, address, category, area))

                if c.rowcount:
                    inserted += 1
                else:
                    duplicates += 1

            except Exception as e:
                print("Error:", e)

    conn.commit()
    conn.close()

    print(f"✅ Inserted: {inserted}")
    print(f"⚠️ Duplicates ignored: {duplicates}")

# -------------------- GET DATA --------------------
def get_leads(search="", category="", area="", status="", sort="name"):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")

    if category:
        query += " AND category = ?"
        params.append(category)

    if area:
        query += " AND area = ?"
        params.append(area)

    if status:
        query += " AND status = ?"
        params.append(status)

    if sort in ["name", "area", "category", "status"]:
        query += f" ORDER BY {sort}"

    c.execute(query, params)
    data = c.fetchall()
    conn.close()
    return data


def get_stats():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM leads")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM leads WHERE status='NEW'")
    new = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM leads WHERE status='CONTACTED'")
    contacted = c.fetchone()[0]

    conn.close()

    return total, new, contacted


# -------------------- UPDATE STATUS --------------------
@app.route("/update/<int:id>/<status>")
def update_status(id, status):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE leads SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

# -------------------- HOME --------------------
@app.route("/")
def home():
    search = request.args.get("search", "")
    category = request.args.get("category", "")
    area = request.args.get("area", "")
    status = request.args.get("status", "")
    sort = request.args.get("sort", "name")

    leads = get_leads(search, category, area, status, sort)

    total, new, contacted = get_stats()

    return render_template_string(
        TEMPLATE,
        leads=leads,
        total=total,
        new=new,
        contacted=contacted
    )

@app.route("/build/<int:id>")
def build_website(id):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM leads WHERE id=?", (id,))
    lead = c.fetchone()
    conn.close()

    if not lead:
        return "Lead not found"

    # 📁 Folder name (clean)
    folder_name = lead["name"].replace(" ", "-").replace("'", "")
    folder_path = os.path.join("sites", folder_name)

    os.makedirs(folder_path, exist_ok=True)

    # 📄 Load template
    with open("template.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 🔥 Inject data into CONFIG
    config_script = f"""
    const CONFIG = {{
      business_name: "{lead['name']}",
      location: "{lead['area']}",
      phone: "{lead['phone']}",
      whatsapp_message: "Hi I saw your business and wanted to book an appointment",
      facebook: "#",
      instagram: "#",
      x: "#",
      youtube: "#"
    }};
    """

    # Replace CONFIG block
    import re
    html = re.sub(r"const CONFIG = \{.*?\};", config_script, html, flags=re.DOTALL)

    # 💾 Save file
    with open(os.path.join(folder_path, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # 🚀 Upload to GitHub
    url = upload_to_github(folder_name)

    return f"✅ Website Live: <a href='{url}' target='_blank'>{url}</a>"

# -------------------- UI TEMPLATE --------------------
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>CRM</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background:#f8f9fa; }
.card { border:none; border-radius:12px; }
.table th { font-weight:600; }
.badge-new { background:#0d6efd; }
.badge-contacted { background:#198754; }
.badge-closed { background:#dc3545; }
</style>
</head>

<body>

<div class="container py-4">

<h3 class="mb-4">🚀 Leads CRM</h3>

<!-- STATS -->
<div class="row mb-4">
  <div class="col-md-4">
    <div class="card p-3 text-center shadow-sm">
      <h6>Total Leads</h6>
    <h4>{{total}}</h4>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card p-3 text-center shadow-sm">
      <h6>New</h6>
     <h4>{{new}}</h4>
<h4>{{contacted}}</h4>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card p-3 text-center shadow-sm">
      <h6>Contacted</h6>
      <h4>{{leads|selectattr('status','equalto','CONTACTED')|list|length}}</h4>
    </div>
  </div>
</div>

<!-- FILTER -->
<form method="get" class="row g-2 mb-3">

  <div class="col-md-3">
    <input name="search" value="{{request.args.get('search','')}}" 
           class="form-control" placeholder="Search name">
  </div>

  <div class="col-md-2">
    <input name="category" value="{{request.args.get('category','')}}" 
           class="form-control" placeholder="Category">
  </div>

  <div class="col-md-2">
    <input name="area" value="{{request.args.get('area','')}}" 
           class="form-control" placeholder="Area">
  </div>

  <div class="col-md-2">
    <select name="status" class="form-select">
      <option value="">All Status</option>
      <option value="NEW">NEW</option>
      <option value="CONTACTED">CONTACTED</option>
      <option value="CLOSED">CLOSED</option>
    </select>
  </div>

  <div class="col-md-2">
    <select name="sort" class="form-select">
      <option value="name">Name</option>
      <option value="area">Area</option>
      <option value="category">Category</option>
      <option value="status">Status</option>
    </select>
  </div>

  <div class="col-md-1">
    <button class="btn btn-dark w-100">Go</button>
  </div>

</form>

<!-- TABLE -->
<div class="card shadow-sm">
<table class="table table-hover mb-0">
<thead class="table-light">
<tr>
<th>Name</th>
<th>Phone</th>
<th>Category</th>
<th>Area</th>
<th>Status</th>
<th>Actions</th>
</tr>
</thead>

<tbody>
{% for lead in leads %}
<tr>

<td>{{lead['name']}}</td>

<td>
  <a href="tel:{{lead['phone']}}" class="text-decoration-none">
    {{lead['phone']}}
  </a>
</td>

<td>{{lead['category']}}</td>
<td>{{lead['area']}}</td>

<td>
{% if lead['status'] == 'NEW' %}
<span class="badge badge-new">NEW</span>
{% elif lead['status'] == 'CONTACTED' %}
<span class="badge badge-contacted">CONTACTED</span>
{% else %}
<span class="badge badge-closed">CLOSED</span>
{% endif %}
</td>

<td class="d-flex gap-1">

<a href="/update/{{lead['id']}}/CONTACTED" 
   class="btn btn-sm btn-success">✓</a>

<a href="/update/{{lead['id']}}/CLOSED" 
   class="btn btn-sm btn-danger">✕</a>

<a target="_blank"
   href="https://wa.me/{{lead['phone']}}?text=Hi%20I%20created%20a%20free%20website%20for%20your%20business"
   class="btn btn-sm btn-primary">WA</a>

   <a href="/build/{{lead['id']}}" 
   class="btn btn-sm btn-dark">Build</a>


</td>

</tr>
{% endfor %}
</tbody>

</table>
</div>

</div>

</body>
</html>
"""

# -------------------- RUN --------------------
if __name__ == "__main__":
    init_db()
    import_csv()  # 🔥 auto import + clean + deduplicate
    app.run(debug=True)
