import time
import os
import re
import PyPDF2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION (FILL THESE IN) ---
# 1. Update the path to your WebDriver executable (e.g., ChromeDriver)
# If you are using a recent version of Selenium, you may not need this line
# DRIVER_PATH = '/path/to/your/chromedriver' 
TARGET_URL = 'https://www.atmosenergy.com/accountcenter/logon/login.html'

# 2. Enter your actual credentials securely (e.g., read from environment variables)
USERNAME = os.getenv('ATMOS_USERNAME')
PASSWORD = os.getenv('ATMOS_PASSWORD') 

# 3. Output file path
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloaded_bills', 'Gas_Bills') # Bills will be saved here

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def setup_driver_options():
    """Sets up Chrome options to handle file downloads automatically."""
    options = webdriver.ChromeOptions()
    # Setting preferences to automatically download PDFs without opening the viewer
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True  # Crucial for direct PDF download
    }
    options.add_experimental_option("prefs", prefs)
    return options

def parse_gas_bill_pdf(pdf_filepath):
    """Extracts account number, amount due, due date, and service dates from the gas bill PDF."""
    
    try:
        with open(pdf_filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            full_text = ""
            for page in pdf_reader.pages:
                full_text += page.extract_text() + "\n"
            
            print("\n--- Parsing Gas Bill PDF Content ---")
            print(f"Extracted {len(full_text)} characters from PDF")
            
            # Initialize variables
            total_amount = "Not Found"
            service_from = "Not Found"
            service_to = "Not Found"
            
            # Patterns based on actual gas bill format
            amount_patterns = [
                r'TOTAL\s+AMOUNT\s+DUE\s+\$([0-9,]+\.?[0-9]*)',
                r'Total\s+Amount\s+Due\s+\$([0-9,]+\.?[0-9]*)',
                r'TOTAL\s+DUE\s+\$([0-9,]+\.?[0-9]*)',
            ]
            
            service_date_patterns = [
                r'Date\s+of\s+Service.*?From\s+To.*?([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})',
                r'([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}).*?Actual\s+Usage',
            ]
            
            # Search for total amount
            for pattern in amount_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    total_amount = f"${match.group(1).strip()}"
                    break
            
            # Search for service dates
            for pattern in service_date_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
                if match:
                    service_from = match.group(1).strip()
                    service_to = match.group(2).strip()
                    break
            
            # Print extracted information
            print(f"Total Amount Due: {total_amount}")
            print(f"Service From: {service_from}")
            print(f"Service To: {service_to}")
            
            return {
                'total_amount': total_amount,
                'service_from': service_from,
                'service_to': service_to,
                'pdf_text': full_text
            }
            
    except Exception as e:
        print(f"ERROR: Could not parse PDF file {pdf_filepath}. Error: {e}")
        return {
            'total_amount': 'Parse Error',
            'service_from': 'Parse Error',
            'service_to': 'Parse Error',
            'pdf_text': ''
        }

def scrape_bill_details(driver):
    """
    Navigates to the Billing and Usage page and focuses only on downloading 
    the latest PDF bill via the new window mechanism.
    """
    # Increased wait time for resilience
    wait = WebDriverWait(driver, 20)
    
    # 1. CLICK THE "Billing and Usage" LINK 
    BILLING_USAGE_LINK_ID = 'viewbills'
    
    try:
        billing_link = wait.until(
            EC.element_to_be_clickable((By.ID, BILLING_USAGE_LINK_ID))
        )
        print("Clicking 'Billing and Usage' link...")
        billing_link.click()
        
        # Wait for the new page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body'))) 
        print(f"Landed on bill history page. Current URL: {driver.current_url}")
        
    except Exception as e:
        print(f"Failed to find or click the 'Billing and Usage' link after login: {e}")
        return None

    # --- PDF DOWNLOAD AND WINDOW SWITCHING LOGIC (Simplified) ---
    
    print("\n--- Downloading Latest Bill PDF ---")

    # Updated XPath for the "View Bills" link that opens the new window
    LATEST_BILL_LINK_XPATH = '/html/body/div/div/section[2]/div/div/div/div[1]/div/div[3]/div/div[2]/table/tbody/tr[1]/td[3]/span/a'
    
    # Data container
    bill_data = {'Item': 'Gas', 'Amount': 'N/A', 'Period': time.strftime("%Y-%m-%d")}

    # Store the main window handle
    main_window_handle = driver.current_window_handle
    
    try:
        # 1. Wait for and click the "View Bills" link (opens new window)
        bill_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, LATEST_BILL_LINK_XPATH))
        )
        print("Found latest bill link. Clicking to open PDF...")
        bill_link.click()
        
        # 2. Wait until a second window handle appears (robust window check)
        print("Waiting for new window to open...")
        
        new_window_handle = None
        start_time = time.time()
        # Poll the window handles until a new one is found (max 20 seconds)
        while (time.time() - start_time) < 20:
            current_handles = driver.window_handles
            if len(current_handles) > 1:
                new_window_handle = [h for h in current_handles if h != main_window_handle][0]
                break
            time.sleep(0.5)

        if new_window_handle:
            # 3. Switch to the new window
            driver.switch_to.window(new_window_handle)
            print(f"Switched to new window (PDF Viewer). URL: {driver.current_url}")
            
            # 4. Wait for the download to complete
            # We must wait long enough for the browser to process the PDF and save it.
            time.sleep(15) 
            
            # 5. Close the PDF window and switch back
            driver.close()
            driver.switch_to.window(main_window_handle)
            print("Closed PDF window and returned to main bill history page.")
        else:
            print("ERROR: New window did not open within the timeout period.")
            # If the download failed, we proceed to file check, which will likely fail too.

        # 6. --- File Renaming Logic ---
        list_of_files = os.listdir(DOWNLOAD_DIR)
        list_of_files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)), reverse=True)
        
        if list_of_files and list_of_files[0].endswith('.pdf'):
            downloaded_filename = list_of_files[0]
            
            # Rename the file using a date fallback
            period_name = time.strftime("%Y-%m-%d_%H%M%S")
            new_filename = f"Gas_Bill_{period_name}.pdf"
            old_path = os.path.join(DOWNLOAD_DIR, downloaded_filename)
            new_path = os.path.join(DOWNLOAD_DIR, new_filename)
            
            os.rename(old_path, new_path)
            print(f"PDF downloaded and renamed to: {new_filename}")
            
            # Parse the PDF content
            pdf_data = parse_gas_bill_pdf(new_path)
            
            # Update bill data with parsed information
            bill_data['Amount'] = pdf_data['total_amount'] if pdf_data['total_amount'] != 'Not Found' else 'N/A'
            bill_data['Period'] = f"{pdf_data['service_from']} to {pdf_data['service_to']}" if pdf_data['service_from'] != 'Not Found' and pdf_data['service_to'] != 'Not Found' else time.strftime("%Y-%m-%d")
            bill_data['Filepath'] = new_path
            
            print(f"\n--- Extracted Bill Information ---")
            print(f"Amount Due: {bill_data['Amount']}")
            print(f"Service Period: {bill_data['Period']}")
        else:
            print("WARNING: Could not locate the downloaded PDF file.")
            
    except Exception as e:
        print(f"WARNING: A fatal error occurred during the bill download process: {e}")
    
    return bill_data

def login_to_portal():
    """
    Uses Selenium to open a browser, navigate to the login page, and submit 
    the username and password.
    """
    options = setup_driver_options()
    
    # Initialize the Chrome driver 
    try:
        # We will let Selenium manage the driver
        driver = webdriver.Chrome(options=options) 
    except Exception as e:
        print(f"Error initializing WebDriver. Ensure Chrome is installed and the driver is accessible.")
        print(f"Details: {e}")
        return None

    try:
        print(f"Opening {TARGET_URL}...")
        driver.get(TARGET_URL)

        # Wait up to 10 seconds until the login form appears
        wait = WebDriverWait(driver, 10)
        
        # --- LOGIN FIELD IDENTIFIERS ---
        # Using the specific XPath you provided for the username
        USERNAME_INPUT_XPATH = '/html/body/div/div/section[2]/div/div/div/div/div[2]/form/input[2]'
        PASSWORD_INPUT_ID = 'password'
        LOGIN_BUTTON_ID = 'authenticate_button_Login' 

        # 1. Find and enter Username using XPath
        username_field = wait.until(
            EC.visibility_of_element_located((By.XPATH, USERNAME_INPUT_XPATH))
        )
        print("Entering username using XPath...")
        username_field.send_keys(USERNAME)
        time.sleep(0.5) 

        # 2. Find and enter Password using ID
        password_field = wait.until(
            EC.visibility_of_element_located((By.ID, PASSWORD_INPUT_ID))
        )
        print("Entering password...")
        password_field.send_keys(PASSWORD)
        time.sleep(0.5) 
        
        # 3. Find and click Login button using ID
        # CHANGED: Use element_to_be_clickable for maximum reliability on buttons
        login_button = wait.until(
            EC.element_to_be_clickable((By.ID, LOGIN_BUTTON_ID))
        )
        print("Clicking login button...")
        login_button.click()

        # Execute the scraping logic and capture the returned data
        bill_data = scrape_bill_details(driver)
        
    except Exception as e:
        print(f"\nAn error occurred during the login process: {e}")
        bill_data = None
        
    finally:
        # Keep the browser open briefly for inspection if an error occurs
        print("\nProcess finished. Closing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()
    
    return bill_data


if __name__ == '__main__':
    if USERNAME == 'YOUR_UTILITY_USERNAME':
        print("!!! SECURITY WARNING !!! Please replace the placeholder USERNAME and PASSWORD in the script before running.")
        print(f"Also, remember to install dependencies: pip install selenium")
    else:
        login_to_portal()
