from flask import Flask, request, jsonify
from config import service, mydb
import re
import threading
import time

app = Flask(__name__)

# Map column indexes to column names in MySQL
column_mapping = {
    1: 'PersonID',
    2: 'LastName',
    3: 'FirstName',
    4: 'Address',
    5: 'City'
}

# Polling interval in seconds
POLLING_INTERVAL = 5  # Adjust as needed

# A tiny function to handle the root route since the 404 can be annoying
@app.route('/', methods=['GET'])
def handle_home():
    print('Flask App Home can be accessed')
    return jsonify({"status": "success"}), 200

# Function to handle the incoming webhook from Google Sheets
@app.route('/webhook', methods=['POST'])
def sync_google_to_mysql():
    data = request.json
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
        # If the primary key, aka, PersonID is removed, it is tantamount to the record being removed and hence we delete it
        if column_number == 1 and new_value == '':
            cursor.execute(f"""
                DELETE FROM persons WHERE PersonID = %s
        """, (row_number, ))
        else:
            cursor.execute(f"""
                UPDATE persons
                SET {column_name} = %s
                WHERE PersonID = %s
            """, (new_value, row_number,))
            # Now we check if any record has all its values apart from primary key empty, essentially a null record. We will consider deleting all information about a record is equivalent to deleting the record
            cursor.execute(f"""
                SELECT * FROM persons WHERE PersonID = %s
            """, (row_number,))
            res = cursor.fetchall()
            flag = False
            for i in res:
                if i[1] == '' and i[2] == '' and i[3] == '' and i[4] == '':
                    flag = True
            if flag:
                cursor.execute(f"""
                    DELETE FROM persons WHERE PersonID = %s
            """, (row_number, ))
    else:
        # Insert a new record if it doesn't exist
        values = [row_number, '', '', '', '']  # Default values as None results in an error

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

def poll_mysql_for_changes():
    while True:
        cursor = mydb.cursor(dictionary=True)
        
        # Select the most recent entry for each PersonID
        cursor.execute("""
            SELECT u1.*
            FROM updates u1
            INNER JOIN (
                SELECT PersonID, MAX(timestamp) AS max_timestamp
                FROM updates
                GROUP BY PersonID
            ) u2
            ON u1.PersonID = u2.PersonID AND u1.timestamp = u2.max_timestamp
        """)
        changes = cursor.fetchall()

        if changes:
            for change in changes:
                print(change)
                action = change['operation']
                record = {
                    'PersonID': change['PersonID'],
                    'LastName': change['LastName'],
                    'FirstName': change['FirstName'],
                    'Address': change['Address'],
                    'City': change['City']
                }

                if action == 'INSERT':
                    # Insert the new record into the Google Sheet
                    body = {
                        'values': [[record['PersonID'], record['LastName'], record['FirstName'], record['Address'], record['City']]]
                    }
                    service.spreadsheets().values().append(
                        spreadsheetId='1mTjh5EtYlD-6aZQ4-P4vNl8bv2QZJQWcC-5_Btp8k1Y', 
                        range="persons!A1:E", 
                        valueInputOption="RAW", 
                        body=body
                    ).execute()

                elif action == 'UPDATE':
                    # Rewrite the entire row in the Google Sheet
                    row_number = record['PersonID']  # Assuming PersonID maps to the row number
                    body = {
                        'values': [[record['PersonID'], record['LastName'], record['FirstName'], record['Address'], record['City']]]
                    }
                    range_ = f'persons!A{int(row_number) + 1}:E{int(row_number) + 1}'  # Update the entire row

                    service.spreadsheets().values().update(
                        spreadsheetId='1mTjh5EtYlD-6aZQ4-P4vNl8bv2QZJQWcC-5_Btp8k1Y', 
                        range=range_, 
                        valueInputOption="RAW", 
                        body=body
                    ).execute()

                elif action == 'DELETE':
                    # Delete the row from Google Sheet (clear the values)
                    row_number = record['PersonID']
                    service.spreadsheets().values().clear(
                        spreadsheetId='1mTjh5EtYlD-6aZQ4-P4vNl8bv2QZJQWcC-5_Btp8k1Y', 
                        range=f'persons!A{int(row_number) + 1}:E{int(row_number) + 1}'
                    ).execute()

            # Clear the update table after processing
            cursor.execute("DELETE FROM updates")
            mydb.commit()

        cursor.close()
        time.sleep(POLLING_INTERVAL)  # Wait before polling again

# Start the polling thread
polling_thread = threading.Thread(target=poll_mysql_for_changes)
polling_thread.daemon = True
polling_thread.start()

if __name__ == '__main__':
    app.run(port=5000)
