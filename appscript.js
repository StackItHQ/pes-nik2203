const WEBHOOK_URL = 'https://17df-2401-4900-8838-1bfc-4cb-4eaf-568e-5675.ngrok-free.app/webhook'; // Replace with your Flask webhook URL


function onEdit(e) {
  var event = e;
  var sheet = e.source.getActiveSheet(); 
  var range = e.range;                   
  var values = range.getValues();        
  
  // Prepare the data to be sent to the webhook
  var data = {
    event: event,
    sheetName: sheet.getName(),          
    range: range.getA1Notation(),        // Get the A1 notation of the edited range (e.g., 'A1:B2')
    values: values                       
  };
  
  sendWebhook(JSON.stringify(data));
}


function sendWebhook(payload) {
  var options = {
    'method': 'post',                    
    'contentType': 'application/json',   
    'payload': payload                   
  };
  
  // Send the POST request to the Flask webhook
  UrlFetchApp.fetch(WEBHOOK_URL, options);
}
