import time
import os
import re
from selenium import webdriver
import PyPDF2
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION (FILL THESE IN) ---

# 1. Utility Configuration (NOW TARGETING DALLAS TRASH BILL)
UTILITY_NAME = 'Trash'
TARGET_URL = 'https://dallasgo.dallas.gov/cp/dwu'
BILLING_USAGE_LINK_ID = 'PLACEHOLDER_ID_BILLING_LINK' # Placeholder for future scraping
# The XPath for the link that opens the latest bill PDF
LATEST_BILL_LINK_SELECTOR = "a.btn-action[title*='View Bill']" 

# 2. Credential and Path Setup
USERNAME = os.getenv('DALLAS_WATER_USERNAME')
PASSWORD = os.getenv('DALLAS_WATER_PASSWORD') 

# IMPORTANT: This path is for session caching! 
# Chrome will save cookies and session info here. If you delete this folder, 
# you will have to log in again. Use a relative path for easy management.
CHROME_PROFILE_PATH = os.path.join(os.getcwd(), 'chrome_profile') 

# Output file path
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloaded_bills', 'Water_and_Trash_Bills') # Bills will be saved here

# Timing constants
PDF_DOWNLOAD_WAIT_TIME = 15 # Seconds to wait for the PDF download to complete

# Ensure necessary directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(CHROME_PROFILE_PATH, exist_ok=True)


def setup_driver_options(profile_path):
    """Sets up Chrome options for downloads and session caching."""
    options = webdriver.ChromeOptions()
    
    # 1. Enable Session Caching (Crucial for skipping repeated logins)
    options.add_argument(f"user-data-dir={profile_path}")
    
    # 2. Download Preferences
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        # Prevents PDF from opening in a new tab; forces download instead
        "plugins.always_open_pdf_externally": True 
    }
    options.add_experimental_option("prefs", prefs)
    return options

def rename_downloaded_file(download_dir, prefix="Utilities_and_Services"):
    """Finds the most recently downloaded PDF and renames it with the specified prefix."""
    
    # Find all files in the download directory
    files = [f for f in os.listdir(download_dir) if f.endswith('.pdf')]
    if not files:
        print("ERROR: No PDF file found in the download directory to rename.")
        return ""
    
    # Find the latest downloaded file (by modification time)
    latest_file_path = max([os.path.join(download_dir, f) for f in files], key=os.path.getmtime)
    latest_filename = os.path.basename(latest_file_path)
    
    # Create the new filename with prefix
    new_filename = f"{prefix}_{latest_filename}"
    new_filepath = os.path.join(download_dir, new_filename)
    
    try:
        os.rename(latest_file_path, new_filepath)
        print(f"PDF downloaded and renamed to: {new_filename}")
        return new_filepath
    except Exception as e:
        print(f"WARNING: Could not rename file {latest_filename}. Error: {e}")
        return latest_file_path # Return original path if rename fails

def parse_pdf_content(pdf_filepath):
    """Extracts invoice number, total amount due, and service dates from the PDF."""
    
    try:
        with open(pdf_filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            full_text = ""
            for page in pdf_reader.pages:
                full_text += page.extract_text() + "\n"
            
            print("\n--- Parsing PDF Content ---")
            print(f"Extracted {len(full_text)} characters from PDF")
            
            # Initialize variables
            invoice_number = "Not Found"
            total_amount = "Not Found"
            service_from = "Not Found"
            service_to = "Not Found"
            
            # Patterns to search for (based on actual PDF format)
            invoice_patterns = [
                r'Invoice\s+Issued\s+[0-9/]+\s+([0-9]+)',  # "Invoice\nIssued\n10/1/25\n051302243946"
                r'([0-9]{12})',  # 12-digit invoice number directly
                r'Invoice.*?([0-9]{10,})',  # Invoice followed by 10+ digit number
            ]
            
            amount_patterns = [
                r'T\s*otal\s+Amount\s+Due\s+\$([0-9,]+\.?[0-9]*)',  # "Total Amount Due $83.90"
                r'Total\s+Amount\s+Due\s+\$([0-9,]+\.?[0-9]*)',
                r'Amount\s+Due\s+\$([0-9,]+\.?[0-9]*)',
            ]
            
            date_patterns = [
                r'Service\s+from\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})',  # "Service from 9/3/25"
            ]
            
            to_date_patterns = [
                r'Service\s+from\s+[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}\s+to\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})',  # "to 10/1/25"
            ]
            
            # Search for invoice number
            for pattern in invoice_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
                if match:
                    invoice_number = match.group(1).strip()
                    break
            
            # Search for total amount
            for pattern in amount_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    total_amount = f"${match.group(1).strip()}"
                    break
            
            # Search for service from date
            for pattern in date_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    service_from = match.group(1).strip()
                    break
            
            # Search for service to date
            for pattern in to_date_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    service_to = match.group(1).strip()
                    break
            
            # Print extracted information
            print(f"Invoice Number: {invoice_number}")
            print(f"Total Amount Due: {total_amount}")
            print(f"Service From: {service_from}")
            print(f"Service To: {service_to}")
            
            return {
                'invoice_number': invoice_number,
                'total_amount': total_amount,
                'service_from': service_from,
                'service_to': service_to,
                'pdf_text': full_text  # Include full text for debugging if needed
            }
            
    except Exception as e:
        print(f"ERROR: Could not parse PDF file {pdf_filepath}. Error: {e}")
        return {
            'invoice_number': 'Parse Error',
            'total_amount': 'Parse Error',
            'service_from': 'Parse Error',
            'service_to': 'Parse Error',
            'pdf_text': ''
        }

def scrape_bill_details(driver):
    """Clicks the bill link, handles the new window, and initiates the PDF download."""
    wait = WebDriverWait(driver, 10)
    
    # Placeholder values for now, as we only have the link XPath
    bill_amount = 'N/A'
    bill_period = time.strftime("%Y-%m-%d")

    print("\n--- Downloading Latest Bill PDF ---")

    try:
        # Store the current window handle (the main dashboard)
        main_window_handle = driver.current_window_handle
        
        # 1. Click the latest bill link using the new CSS Selector
        bill_link = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, LATEST_BILL_LINK_SELECTOR))
        )
        print("Found latest bill link. Clicking to open PDF...")
        
        # Ensure the element is in view before clicking
        driver.execute_script("arguments[0].scrollIntoView(true);", bill_link)
        bill_link.click()

        # Wait for the PDF download to complete
        print("Waiting for PDF download to complete...")
        time.sleep(PDF_DOWNLOAD_WAIT_TIME)
        
        # Rename the downloaded file with prefix
        renamed_filepath = rename_downloaded_file(DOWNLOAD_DIR)
        if renamed_filepath:
            print(f"File successfully renamed and saved at: {renamed_filepath}")
            
            # Parse the PDF content
            pdf_data = parse_pdf_content(renamed_filepath)
            
            # Update bill data with parsed information
            bill_amount = pdf_data['total_amount'] if pdf_data['total_amount'] != 'Not Found' else 'N/A'
            bill_period = f"{pdf_data['service_from']} to {pdf_data['service_to']}" if pdf_data['service_from'] != 'Not Found' and pdf_data['service_to'] != 'Not Found' else time.strftime("%Y-%m-%d")
            
            print(f"\n--- Extracted Bill Information ---")
            print(f"Invoice Number: {pdf_data['invoice_number']}")
            print(f"Amount Due: {bill_amount}")
            print(f"Service Period: {bill_period}")
            
            return {
                'Item': UTILITY_NAME,
                'Amount': bill_amount,
                'Period': bill_period,
                'Invoice_Number': pdf_data['invoice_number'],
                'Service_From': pdf_data['service_from'],
                'Service_To': pdf_data['service_to'],
                'Filepath': renamed_filepath
            }
        
    except Exception as e:
        print(f"WARNING: An error occurred during the bill download process: {e}")
        # Still attempt to rename any downloaded file even if there was an error
        try:
            renamed_filepath = rename_downloaded_file(DOWNLOAD_DIR)
            if renamed_filepath:
                print(f"File renamed despite error: {renamed_filepath}")
                # Try to parse PDF even if download had issues
                try:
                    pdf_data = parse_pdf_content(renamed_filepath)
                    bill_amount = pdf_data['total_amount'] if pdf_data['total_amount'] != 'Not Found' else 'N/A'
                    bill_period = f"{pdf_data['service_from']} to {pdf_data['service_to']}" if pdf_data['service_from'] != 'Not Found' and pdf_data['service_to'] != 'Not Found' else time.strftime("%Y-%m-%d")
                    return {
                        'Item': UTILITY_NAME,
                        'Amount': bill_amount,
                        'Period': bill_period,
                        'Invoice_Number': pdf_data['invoice_number'],
                        'Service_From': pdf_data['service_from'],
                        'Service_To': pdf_data['service_to'],
                        'Filepath': renamed_filepath
                    }
                except:
                    print("Could not parse PDF due to errors.")
        except:
            print("Could not rename file due to earlier errors.")
        
        return {'Item': UTILITY_NAME, 'Amount': bill_amount, 'Period': bill_period, 'Filepath': 'DOWNLOAD_FAILED'}
        

def login_to_portal():
    """
    Handles driver initialization, login sequence (or session reuse), and 
    delegates to scraping.
    """
    options = setup_driver_options(CHROME_PROFILE_PATH)
    
    try:
        # Initialize Chrome
        driver = webdriver.Chrome(options=options) 
    except Exception as e:
        print(f"Error initializing WebDriver. Ensure Chrome is installed and the driver is accessible.")
        print(f"Details: {e}")
        return None

    wait = WebDriverWait(driver, 10)
    
    try:
        print(f"Opening {TARGET_URL}...")
        driver.get(TARGET_URL)
            
        # --- LOGIN FIELD IDENTIFIERS ---
        USERNAME_INPUT_ID = 'id_loginId' 
        PASSWORD_INPUT_ID = 'id_password'
        # Using the user-provided specific XPath for the submit button
        LOGIN_BUTTON_XPATH = '/html/body/div[2]/div/div[2]/div[2]/div/form/fieldset/div/div[4]/div/input'
        
        # 1. Find and enter Username using ID
        username_field = wait.until(
            EC.visibility_of_element_located((By.ID, USERNAME_INPUT_ID))
        )
        print("Entering username using ID...")
        username_field.send_keys(USERNAME)
        time.sleep(0.5) 

        # 2. Find and enter Password using ID
        password_field = wait.until(
            EC.visibility_of_element_located((By.ID, PASSWORD_INPUT_ID))
        )
        print("Entering password...")
        password_field.send_keys(PASSWORD)
        time.sleep(0.5) 
        
        # 3. Find and click Login button using XPATH
        login_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_XPATH))
        )
        print("Clicking login button...")
        
        try:
            # Attempt a native Selenium click first
            login_button.click()
        except Exception:
            # Fallback to JavaScript if the native click fails
            print("Native click failed. Attempting JavaScript click...")
            driver.execute_script("arguments[0].click();", login_button)
        
        # Wait to ensure the post-login page loads
        time.sleep(5) 


        # Execute the scraping logic (now includes download) and capture the returned data
        bill_data = scrape_bill_details(driver)
        
    except Exception as e:
        print(f"\nAn error occurred during the process: {e}")
        bill_data = None
        
    finally:
        # --- IMPORTANT FOR TESTING ---
        # For quick testing, the browser session is kept open.
        print(f"\n--- Testing complete for {UTILITY_NAME}. The browser session is kept open for faster re-runs. ---")
        print("To fully log out and close the browser, uncomment 'driver.quit()'.")
        # driver.quit()
    
    return bill_data 


if __name__ == '__main__':
    if USERNAME == 'YOUR_DALLAS_USERNAME':
        print("!!! ACTION REQUIRED !!! Please replace the placeholder USERNAME and PASSWORD in the script before running.")
        print(f"Also, remember to install dependencies: pip install selenium")
    else:
        login_to_portal()