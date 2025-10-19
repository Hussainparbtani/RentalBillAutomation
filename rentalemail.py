import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict
import sys
import os
import csv
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import the bill scraping functions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from gasbill import login_to_portal as get_gas_bill
from trashbill import login_to_portal as get_trash_bill

# --- CONFIGURATION ---
# IMPORTANT SECURITY NOTE: 
# If you are using Gmail or other major providers, you MUST use an 'App Password' 
# instead of your regular account password for security and compatibility.
SMTP_SERVER = 'smtp.gmail.com' # Use 'smtp.office365.com' for Outlook/Hotmail
SMTP_PORT = 587 # Port 587 is standard for STARTTLS encryption
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
TENANT_EMAIL = os.getenv('TENANT_EMAIL')
TENANT_NAME = os.getenv('TENANT_NAME')
LANDLORD_NAME = os.getenv('LANDLORD_NAME')
RENT_AMOUNT = f"${os.getenv('RENT_AMOUNT')}"
TRACKING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sent_emails.csv')

def check_already_sent(year: int, month: int) -> bool:
    """Check if an email has already been sent for the given year and month."""
    if not os.path.exists(TRACKING_FILE):
        return False
    
    try:
        with open(TRACKING_FILE, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if int(row['year']) == year and int(row['month']) == month:
                    return True
    except Exception as e:
        print(f"Warning: Could not read tracking file. Error: {e}")
    
    return False

def record_sent_email(year: int, month: int, bill_details: List[Dict[str, str]], file_paths: List[str]):
    """Record the sent email details to the CSV tracking file."""
    file_exists = os.path.exists(TRACKING_FILE)
    
    # Extract amounts from bill_details
    gas_amount = next((b['Amount'] for b in bill_details if b['Item'] == 'Gas'), 'N/A')
    trash_amount = next((b['Amount'] for b in bill_details if b['Item'] == 'Trash + Water'), 'N/A')
    total_amount = next((b['Amount'] for b in bill_details if 'Total' in b['Item']), 'N/A')
    
    # Extract file paths
    gas_file = next((f for f in file_paths if 'Gas_Bills' in f), '')
    trash_file = next((f for f in file_paths if 'Water_and_Trash_Bills' in f), '')
    
    try:
        with open(TRACKING_FILE, 'a', newline='') as csvfile:
            fieldnames = ['timestamp', 'year', 'month', 'gas_amount', 'trash_amount', 'rent_amount', 
                         'total_amount', 'gas_pdf', 'trash_pdf', 'tenant_email']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header if file is new
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'year': year,
                'month': month,
                'gas_amount': gas_amount,
                'trash_amount': trash_amount,
                'rent_amount': RENT_AMOUNT,
                'total_amount': total_amount,
                'gas_pdf': os.path.basename(gas_file) if gas_file else '',
                'trash_pdf': os.path.basename(trash_file) if trash_file else '',
                'tenant_email': TENANT_EMAIL
            })
        print(f"\n✓ Recorded email send to tracking file: {TRACKING_FILE}")
    except Exception as e:
        print(f"Warning: Could not write to tracking file. Error: {e}")

def fetch_utility_bills() -> tuple[List[Dict[str, str]], List[str]]:
    """Fetches gas and trash bill data by running the scraping scripts.
    Returns: (bill_details, file_paths)
    """
    
    print("=== Fetching Gas Bill ===")
    gas_data = get_gas_bill()
    
    print("\n=== Fetching Trash/Water Bill ===")
    trash_data = get_trash_bill()
    
    # Check if both bills were successfully retrieved
    if not gas_data:
        raise Exception("Failed to retrieve gas bill data. Aborting email send.")
    if not trash_data:
        raise Exception("Failed to retrieve trash/water bill data. Aborting email send.")
    
    # Track file paths for attachments
    file_paths = []
    
    # Extract the data, handling None returns
    gas_amount = gas_data.get('Amount', 'N/A')
    gas_period = gas_data.get('Period', 'N/A')
    if gas_data.get('Filepath'):
        file_paths.append(gas_data.get('Filepath'))
    
    trash_amount = trash_data.get('Amount', 'N/A')
    trash_period = trash_data.get('Period', 'N/A')
    if trash_data.get('Filepath'):
        file_paths.append(trash_data.get('Filepath'))
    
    # Build the bill details list
    bill_details = [
        {"Item": "Gas", "Amount": gas_amount, "Notes": gas_period},
        {"Item": "Trash + Water", "Amount": trash_amount, "Notes": trash_period},
        {"Item": "Rent", "Amount": RENT_AMOUNT, "Notes": "For the upcoming month"},
    ]
    
    # Calculate total (convert string amounts to float for calculation)
    total = 0.0
    try:
        for bill in bill_details:
            amount_str = bill['Amount'].replace('$', '').replace(',', '')
            if amount_str != 'N/A':
                total += float(amount_str)
        
        bill_details.append({
            "Item": "Total Due", 
            "Amount": f"${total:,.2f}", 
            "Notes": ""
        })
    except Exception as e:
        print(f"Warning: Could not calculate total. Error: {e}")
        bill_details.append({
            "Item": "Total Due", 
            "Amount": "See individual items", 
            "Notes": ""
        })
    
    return bill_details, file_paths

# --- BILL DATA (Legacy - now generated dynamically) ---
# --- BILL DATA (Legacy - now generated dynamically) ---
# This data drives the content of the table (now fetched automatically)
BILL_DETAILS: List[Dict[str, str]] = []  # Will be populated by fetch_utility_bills()

def create_email_body(tenant_name: str, landlord_name: str, bill_details: List[Dict[str, str]]) -> Dict[str, str]:
    """Generates the plain text and HTML parts of the email."""
    
    # Build plain text table
    plain_table = "Item             | Amount     | Notes\n"
    plain_table += "-----------------|------------|-----------------------\n"
    for detail in bill_details:
        item = detail["Item"].ljust(16)
        amount = detail["Amount"].ljust(10)
        notes = detail["Notes"]
        plain_table += f"{item} | {amount} | {notes}\n"
    
    # 1. Plain Text Body (Fallback for old email clients)
    plain_text = f"""
Hi {tenant_name},

Hope all is well. I've attached the utility bills for the previous month and rent for the upcoming month.

--- Bill Summary ---
{plain_table}---

Please let me know if you have any questions.

Best,
{landlord_name}
"""

    # 2. HTML Body (For formatting the table)
    
    # Build the table rows dynamically
    table_rows = ""
    for detail in bill_details:
        is_total = "Total" in detail["Item"]
        
        # Apply bold/border styling for the Total row
        row_style = "font-weight: bold; border-top: 2px solid #ddd;" if is_total else ""
        
        table_rows += f"""
        <tr style="{row_style}">
            <td style="padding: 10px; border: 1px solid #eee; text-align: left; background-color: {'#f9f9f9' if not is_total else '#e0f7fa'};">{detail['Item']}</td>
            <td style="padding: 10px; border: 1px solid #eee; text-align: right; background-color: {'#f9f9f9' if not is_total else '#e0f7fa'};">{detail['Amount']}</td>
            <td style="padding: 10px; border: 1px solid #eee; text-align: left; background-color: {'#f9f9f9' if not is_total else '#e0f7fa'};">{detail['Notes']}</td>
        </tr>
        """

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <p>Hi {tenant_name},</p>
        <p>Hope all is well. I've attached the utility bills for the previous month and rent for the current month.</p>
        
        <table style="width: 100%; max-width: 600px; border-collapse: collapse; margin: 20px 0; border: 1px solid #ddd;">
          <thead>
            <tr style="background-color: #f1f1f1;">
              <th style="padding: 10px; border: 1px solid #ddd; text-align: left; width: 30%;">Items</th>
              <th style="padding: 10px; border: 1px solid #ddd; text-align: right; width: 20%;">Amount</th>
              <th style="padding: 10px; border: 1px solid #ddd; text-align: left; width: 50%;">Notes</th>
            </tr>
          </thead>
          <tbody>
            {table_rows}
          </tbody>
        </table>

        <p>Please let me know if you have any questions.</p>
        <p>Best,<br>{landlord_name}</p>
      </body>
    </html>
    """
    
    return {"plain": plain_text.strip(), "html": html.strip()}

def send_bill_email(recipient: str, subject: str, body: Dict[str, str], attachments: List[str] = None):
    """Sends the email using the configured SMTP server with optional PDF attachments."""
    
    msg = MIMEMultipart('alternative')
    msg['From'] = f"{LANDLORD_NAME} <{SENDER_EMAIL}>"
    msg['To'] = recipient
    msg['Subject'] = subject

    # Attach parts into message container.
    # The MIMEText object with 'plain' encoding is first, then 'html'.
    # Email clients will display the last part they can read.
    msg.attach(MIMEText(body["plain"], 'plain'))
    msg.attach(MIMEText(body["html"], 'html'))
    
    # Attach PDF files if provided
    if attachments:
        for filepath in attachments:
            if os.path.exists(filepath):
                try:
                    filename = os.path.basename(filepath)
                    with open(filepath, 'rb') as attachment_file:
                        part = MIMEBase('application', 'pdf')
                        part.set_payload(attachment_file.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}',
                    )
                    msg.attach(part)
                    print(f"Attached: {filename}")
                except Exception as e:
                    print(f"Warning: Could not attach {filepath}. Error: {e}")
            else:
                print(f"Warning: File not found: {filepath}")

    print(f"Attempting to send email to {recipient}...")
    
    try:
        # Connect to the server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()
        server.starttls()  # Start TLS encryption
        server.ehlo()
        
        # Login to the server
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        # Send the message
        server.sendmail(SENDER_EMAIL, recipient, msg.as_string())
        
        server.quit()
        print("Successfully sent rent and utility bill email!")
        
    except Exception as e:
        print(f"An error occurred while sending the email: {e}")
        print("\nPlease check your SENDER_EMAIL, SENDER_PASSWORD (ensure it's an App Password if needed), and SMTP server/port settings.")

if __name__ == '__main__':
    
    # 1. Check if email already sent for this month
    next_month = datetime.now() + relativedelta(months=1)
    target_year = next_month.year
    target_month = next_month.month
    
    if check_already_sent(target_year, target_month):
        print(f"\n⚠️  Email already sent for {next_month.strftime('%B %Y')}.")
        print(f"Check {TRACKING_FILE} for details.")
        print("\nTo resend, delete the corresponding row from the CSV file and run again.\n")
        sys.exit(0)
    
    # 2. Fetch utility bills from gas and trash scripts
    print("Fetching utility bill information...\n")
    bill_details, attachments = fetch_utility_bills()
    
    # 3. Define the Subject Line (next month's rent)
    subject_line = f"{next_month.strftime('%B %Y')} Rent and Utility Bill Statement"
    
    # 4. Generate the email content
    email_content = create_email_body(TENANT_NAME, LANDLORD_NAME, bill_details)
    
    # 5. Send the email with attachments
    send_bill_email(TENANT_EMAIL, subject_line, email_content, attachments)
    
    # 6. Record the sent email
    record_sent_email(target_year, target_month, bill_details, attachments)
