from crypt import methods
from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import mysql.connector
import os
import re


# Removes need for redundant authentication by checking if already authenticated and valid
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

# Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
service = authenticate_google_sheets()

app = Flask(__name__)

# MySQL connection setup
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="#Nikki2203",
    database="superjoin"
)

# Map column indexes to column names in MySQL
column_mapping = {
    1: 'PersonID',
    2: 'LastName',
    3: 'FirstName',
    4: 'Address',
    5: 'City'
}

# A tiny function to handle the root route since the 404 can be annoying
@app.route('/', methods=['GET'])
def handle_home():
    print('Flask App Home can be accessed')
    return jsonify({"status": "success"}), 200

# Function to handle the incoming webhook from Google Sheets
@app.route('/webhook', methods=['POST'])
def sync_google_to_mysql():
    data = request.json
    # sheet_name = data.get('sheetName', '')
    cell_range = data.get('range', '')
    new_values = data.get('values', [['']])[0]  # Extract changed value(s)
    new_value = new_values[0] if new_values else None  # Get first value from array if present

    # Extract row and column from range
    match = re.match(r"([A-Z]+)(\d+)", cell_range)
    if not match:
        return jsonify({"status": "error", "message": "Invalid range"}), 400

    column_letter, row_number = match.groups()
    row_number = str(int(row_number) - 1)
    column_number = ord(column_letter) - ord('A') + 1  # Convert letter to column number

    # Validate the range falls within the expected column set as currently hardcoded
    if column_number not in column_mapping:
        return jsonify({"status": "error", "message": "Out of range"}), 400

    # Map the column number to the corresponding MySQL column name
    column_name = column_mapping[column_number]

    cursor = mydb.cursor()
    cursor.execute(f"SELECT * FROM persons WHERE PersonID = %s", (row_number,))
    record = cursor.fetchall()

    if record:
        # Update the existing record
        cursor.execute(f"""
            UPDATE persons
            SET {column_name} = %s
            WHERE PersonID = %s
        """, (new_value, row_number,))
    else:
        # Insert a new record if it doesn't exist
        values = [row_number, '0', '0', '0', '0']  # Default values as None results in an error

        # Update the corresponding field with the new value
        values[column_number - 1] = new_value

        cursor.execute(f"""
            INSERT INTO persons (PersonID, LastName, FirstName, Address, City)
            VALUES (%s, %s, %s, %s, %s)
        """, tuple(values))

    mydb.commit()

    return jsonify({"status": "success"}), 200


# Flask route to manually sync MySQL to Google Sheets (if needed)
@app.route('/sync-mysql-to-google', methods=['POST'])
def sync_mysql_to_google():
    data = request.json

    sheet_id = '1mTjh5EtYlD-6aZQ4-P4vNl8bv2QZJQWcC-5_Btp8k1Y'
    range_name = 'Sheet1!A1:E'

    body = {
        'values': [[data['PersonID'], data['LastName'], data['FirstName'], data['Address'], data['City']]]
    }

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=range_name,
        valueInputOption="RAW", body=body).execute()

    return jsonify({"status": "success"}), 200


if __name__ == '__main__':
    app.run(port=5000)
