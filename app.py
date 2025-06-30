from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
import pandas as pd
import sqlite3
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

DATABASE = 'tcwd_database.db'
ITEMS_PER_PAGE = 15

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'tcwd' and request.form['password'] == 'tcwdcic':
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    search = request.args.get('q', '')
    status = request.args.get('status', '')
    bookno = request.args.get('bookno', '')
    page = int(request.args.get('page', 1))

    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    if search:
        query += " AND (Name LIKE ? OR AccountNumber LIKE ? OR MeterNo LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term])

    if status:
        query += " AND Status = ?"
        params.append(status)

    if bookno:
        query += " AND BookNo = ?"
        params.append(bookno)

    offset = (page - 1) * ITEMS_PER_PAGE
    paginated_query = query + " LIMIT ? OFFSET ?"
    params.extend([ITEMS_PER_PAGE, offset])

    conn = get_db_connection()
    rows = conn.execute(paginated_query, params).fetchall()
    all_statuses = [row['Status'] for row in conn.execute("SELECT DISTINCT Status FROM customers").fetchall()]
    all_booknos = [row['BookNo'] for row in conn.execute("SELECT DISTINCT BookNo FROM customers").fetchall()]
    total_rows = conn.execute(f"SELECT COUNT(*) FROM ({query})", params[:-2]).fetchone()[0]
    columns = [description[0] for description in conn.execute("SELECT * FROM customers LIMIT 1").description]
    conn.close()

    total_pages = (total_rows + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    return render_template(
        'index.html',
        rows=rows,
        columns=columns,
        search=search,
        statuses=all_statuses,
        selected_status=status,
        booknos=all_booknos,
        selected_bookno=bookno,
        page=page,
        total_pages=total_pages,
        zip=zip
    )

@app.route('/suggest')
def suggest():
    term = request.args.get('term', '')
    conn = get_db_connection()
    suggestions = conn.execute("""
        SELECT Name FROM customers
        WHERE Name LIKE ? OR AccountNumber LIKE ? OR MeterNo LIKE ?
        LIMIT 5
    """, (f'%{term}%', f'%{term}%', f'%{term}%')).fetchall()
    conn.close()
    return jsonify([row['Name'] for row in suggestions])

@app.route('/export')
def export():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    search = request.args.get('q', '')
    status = request.args.get('status', '')
    bookno = request.args.get('bookno', '')
    format = request.args.get('format', 'csv')

    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    if search:
        query += " AND (Name LIKE ? OR AccountNumber LIKE ? OR MeterNo LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term])

    if status:
        query += " AND Status = ?"
        params.append(status)

    if bookno:
        query += " AND BookNo = ?"
        params.append(bookno)

    conn = get_db_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    output = io.BytesIO()
    if format == 'excel':
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
        output.seek(0)
        return send_file(output, download_name="filtered_data.xlsx", as_attachment=True)
    else:
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(output, download_name="filtered_data.csv", as_attachment=True, mimetype='text/csv')

if __name__ == '__main__':
    app.run(debug=True)