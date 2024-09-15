const WEBHOOK_URL = 'https://17df-2401-4900-8838-1bfc-4cb-4eaf-568e-5675.ngrok-free.app/webhook'; // Replace with your Flask webhook URL

// Function triggered when a user edits the Google Sheet
function onEdit(e) {
  var event = e;
  var sheet = e.source.getActiveSheet(); // Get the active sheet that was edited
  var range = e.range;                   // Get the range of cells that were edited
  var values = range.getValues();        // Get the new values of the edited cells
  
  // Prepare the data to be sent to the webhook
  var data = {
    event: event,
    sheetName: sheet.getName(),          // Get the name of the sheet
    range: range.getA1Notation(),        // Get the A1 notation of the edited range (e.g., 'A1:B2')
    values: values                       // Get the new values of the cells in the edited range
  };
  
  // Send the data to the backend webhook
  sendWebhook(JSON.stringify(data));
}

// Function to send the data to the Flask webhook
function sendWebhook(payload) {
  var options = {
    'method': 'post',                    // POST request
    'contentType': 'application/json',   // Sending JSON data
    'payload': payload                   // Data to send (sheet name, range, values)
  };
  
  // Send the POST request to the Flask webhook
  UrlFetchApp.fetch(WEBHOOK_URL, options);
}
