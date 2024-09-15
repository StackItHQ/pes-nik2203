from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import mysql.connector
import os

app = Flask(__name__)

# Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

# Authenticate with Google Sheets API
def authenticate_google_sheets():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('sheets', 'v4', credentials=creds)
    return service

# MySQL Connection
def get_mysql_connection():
    connection = mysql.connector.connect(
        host="localhost",  # Replace with your DB host
        user="root",
        password="#Nikki2203",
        database="superjoin"
    )
    return connection

# Create MySQL Table from Google Sheet Data
def create_mysql_table_from_sheet(sheet_name, data):
    connection = get_mysql_connection()
    cursor = connection.cursor()

    # Extract headers
    headers = data[0]
    for i in range(len(headers)):
        headers[i] = ''.join(headers[i].split(' '))
    print(headers)
    for i in headers:
        print(i)
    # Create table query
    create_query = f"CREATE TABLE IF NOT EXISTS {sheet_name} ("
    create_query += ", ".join([f"{header} VARCHAR(255)" for header in headers])
    create_query += ");"
    print(create_query)

    cursor.execute(create_query)
    connection.commit()
    cursor.execute(f"DESC {sheet_name};")
    desc = cursor.fetchall()
    print(desc)    
    # Insert Data into the new table
    for row in data[1:]:
        insert_query = f"INSERT INTO {sheet_name} ({', '.join(headers)}) VALUES ({', '.join(['%s'] * len(row))})"
        cursor.execute(insert_query, row)
    
    connection.commit()
    cursor.close()
    connection.close()

# Create Google Sheet from MySQL Table
def create_google_sheet_from_mysql(table_name):
    service = authenticate_google_sheets()
    connection = get_mysql_connection()
    cursor = connection.cursor()

    # Fetch table data from MySQL
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    # Fetch table columns (headers)
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    columns = [column[0] for column in cursor.fetchall()]

    # Create a new Google Sheet
    sheet_body = {
        'properties': {
            'title': table_name
        }
    }
    sheet = service.spreadsheets().create(body=sheet_body).execute()
    sheet_id = sheet['spreadsheetId']

    # Insert Data into Google Sheet
    values = [columns] + rows
    body = {
        'values': values
    }
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range="A1",
        valueInputOption="RAW", body=body).execute()

    cursor.close()
    connection.close()

    return sheet_id

@app.route('/', methods=['GET'])
def handle_home():
    return jsonify({"status": "success"}) , 200

# Webhook to handle Google Sheets changes
@app.route('/webhook', methods=['POST'])
def handle_sheet_webhook():
    data = request.json
    sheet_name = data.get('sheetName')
    range_ = data.get('range')
    values = data.get('values')

    # Create MySQL table from Google Sheet if it doesn't exist
    create_mysql_table_from_sheet(sheet_name, values)
    
    return jsonify({"status": "success"}), 200

# Sync MySQL to Google Sheets
@app.route('/sync_mysql_to_sheets', methods=['POST'])
def sync_mysql_to_sheets():
    table_name = request.json.get('table_name')
    sheet_id = create_google_sheet_from_mysql(table_name)
    return jsonify({"status": "Google Sheet created", "sheet_id": sheet_id}), 200

if __name__ == '__main__':
    app.run(port=5000)
