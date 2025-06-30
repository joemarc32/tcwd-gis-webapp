from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import pandas as pd
import io
import os

app = Flask(__name__)

DB_FILE = 'tcwd_database.db'
TABLE = 'customers'

@app.route('/', methods=['GET'])
def index():
    search = request.args.get('q', '')
    status_filter = request.args.get('status', '')
    bookno_filter = request.args.get('bookno', '')
    page = int(request.args.get('page', 1))
    per_page = 15
    offset = (page - 1) * per_page

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    like = f'%{search}%'

    # Count total rows
    count_sql = f"SELECT COUNT(*) FROM {TABLE} WHERE 1=1"
    count_params = []

    if search:
        count_sql += " AND (AccountNumber LIKE ? OR MeterNo LIKE ? OR Name LIKE ?)"
        count_params.extend([like, like, like])
    if status_filter:
        count_sql += " AND Status = ?"
        count_params.append(status_filter)
    if bookno_filter:
        count_sql += " AND BookNo = ?"
        count_params.append(bookno_filter)

    cursor.execute(count_sql, count_params)
    total_rows = cursor.fetchone()[0]
    total_pages = (total_rows + per_page - 1) // per_page

    # Retrieve paginated data
    sql = f"SELECT * FROM {TABLE} WHERE 1=1"
    params = []

    if search:
        sql += " AND (AccountNumber LIKE ? OR MeterNo LIKE ? OR Name LIKE ?)"
        params.extend([like, like, like])
    if status_filter:
        sql += " AND Status = ?"
        params.append(status_filter)
    if bookno_filter:
        sql += " AND BookNo = ?"
        params.append(bookno_filter)

    sql += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    # Get filter dropdowns
    cursor.execute(f"SELECT DISTINCT Status FROM {TABLE} ORDER BY Status ASC")
    statuses = [row[0] for row in cursor.fetchall()]
    cursor.execute(f"SELECT DISTINCT BookNo FROM {TABLE} ORDER BY BookNo ASC")
    booknos = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template(
        'index.html',
        rows=rows,
        columns=columns,
        search=search,
        selected_status=status_filter,
        selected_bookno=bookno_filter,
        page=page,
        total_pages=total_pages,
        statuses=statuses,
        booknos=booknos
    )

@app.route('/suggest')
def suggest():
    term = request.args.get('term', '')
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    sql = f"""
    SELECT DISTINCT suggestion FROM (
        SELECT AccountNumber AS suggestion FROM {TABLE} WHERE AccountNumber LIKE ?
        UNION
        SELECT MeterNo FROM {TABLE} WHERE MeterNo LIKE ?
        UNION
        SELECT Name FROM {TABLE} WHERE Name LIKE ?
    )
    ORDER BY suggestion ASC
    LIMIT 5
    """
    like_term = f'%{term}%'
    cursor.execute(sql, (like_term, like_term, like_term))
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(results)

@app.route('/export')
def export():
    search = request.args.get('q', '')
    status_filter = request.args.get('status', '')
    bookno_filter = request.args.get('bookno', '')
    format_type = request.args.get('format', 'csv')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    sql = f"SELECT * FROM {TABLE} WHERE 1=1"
    params = []

    if search:
        like = f'%{search}%'
        sql += " AND (AccountNumber LIKE ? OR MeterNo LIKE ? OR Name LIKE ?)"
        params.extend([like, like, like])
    if status_filter:
        sql += " AND Status = ?"
        params.append(status_filter)
    if bookno_filter:
        sql += " AND BookNo = ?"
        params.append(bookno_filter)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    df = pd.DataFrame(rows, columns=columns)

    if format_type == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Filtered Data')
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='filtered_data.xlsx'
        )
    else:
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='filtered_data.csv'
        )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
