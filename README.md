# RentalBillAutomation

An automated system that scrapes utility bills (gas and water/trash) from provider websites, extracts billing information using PDF parsing, and sends a formatted monthly statement email to tenants with bill details and PDF attachments.

## Features

- 🔄 **Automated Bill Scraping**: Logs into Dallas Water Utilities and Atmos Energy portals using Selenium WebDriver
- 📄 **PDF Parsing**: Extracts invoice numbers, amounts, and service periods from downloaded bill PDFs
- 📧 **Email Automation**: Sends professionally formatted HTML emails with PDF attachments
- 🔒 **Secure Configuration**: All credentials stored in `.env` file (not committed to git)
- 📊 **Tracking System**: CSV-based audit trail (`sent_emails.csv`) to track all sent emails
- 🚫 **Duplicate Prevention**: Prevents sending multiple emails for the same billing period
- 📁 **Organized Storage**: Automatically organizes bills into `Gas_Bills/` and `Water_and_Trash_Bills/` folders
- ✅ **Error Handling**: Aborts email if either utility bill fails to retrieve

## Project Structure

```
RentalBillAutomation/
├── gasbill.py              # Scrapes Atmos Energy gas bills
├── trashbill.py            # Scrapes Dallas Water Utilities trash/water bills
├── rentalemail.py          # Main script - orchestrates scraping and email sending
├── requirements.txt        # Python dependencies
├── .env                    # Credentials (not committed)
├── .env.example            # Template for environment variables
├── .gitignore              # Git exclusions
├── sent_emails.csv         # Audit trail of sent emails
└── downloaded_bills/
    ├── Gas_Bills/
    └── Water_and_Trash_Bills/
```

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Hussainparbtani/RentalBillAutomation.git
cd RentalBillAutomation
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your information:

```bash
# Dallas Water Utilities Credentials
DALLAS_WATER_USERNAME=your_dallas_username@example.com
DALLAS_WATER_PASSWORD=your_dallas_password

# Atmos Energy (Gas) Credentials
ATMOS_USERNAME=your_atmos_username@example.com
ATMOS_PASSWORD=your_atmos_password

# Email Configuration (Use App Password for Gmail)
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
TENANT_EMAIL=tenant_email@example.com

# Tenant and Landlord Information
TENANT_NAME=TenantFirstName
LANDLORD_NAME=YourName
RENT_AMOUNT=2900.00
```

**Important:** For Gmail, you must use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

### 5. Install Chrome WebDriver

The script requires Chrome and ChromeDriver:

- **macOS**: `brew install chromedriver`
- **Linux**: `sudo apt-get install chromium-chromedriver`
- **Windows**: Download from [ChromeDriver](https://chromedriver.chromium.org/)

## Usage

### Run the Script

```bash
python rentalemail.py
```

### What Happens:

1. **Duplicate Check**: Verifies if email already sent for current month
2. **Bill Scraping**: Logs into both utility portals and downloads latest bills
3. **PDF Parsing**: Extracts amounts, invoice numbers, and service periods
4. **Email Generation**: Creates HTML-formatted email with dynamic subject line
5. **Send Email**: Emails tenant with PDF attachments
6. **Record Keeping**: Logs details to `sent_emails.csv`

### Email Format

**Subject:** `November 2025 Rent and Utility Bill Statement`

**Body:** Formatted HTML table with:
- Gas bill amount and service period
- Trash + Water bill amount and service period
- Rent amount
- **Total Due**

**Attachments:** Gas and Water/Trash bill PDFs

## Tracking & Audit Trail

All sent emails are logged to `sent_emails.csv`:

| Field | Description |
|-------|-------------|
| `timestamp` | When email was sent |
| `year` | Target billing year |
| `month` | Target billing month |
| `gas_amount` | Gas bill amount |
| `trash_amount` | Trash/water bill amount |
| `rent_amount` | Monthly rent |
| `total_amount` | Total due |
| `gas_pdf` | Gas bill filename |
| `trash_pdf` | Trash/water bill filename |
| `tenant_email` | Recipient email |

### Resending an Email

If you need to resend for the same month:

1. Delete the corresponding row from `sent_emails.csv`
2. Run `python rentalemail.py` again

## Dependencies

- **selenium** (4.37.0): Browser automation for web scraping
- **PyPDF2** (3.0.1): PDF text extraction and parsing
- **python-dotenv** (1.1.1): Environment variable management
- **python-dateutil** (2.9.0): Date manipulation for dynamic subject lines

## Security Notes

- ⚠️ **Never commit** `.env` file to version control
- Use App Passwords for email providers (especially Gmail)
- Keep `sent_emails.csv` backed up for audit purposes
- Bills are stored locally in `downloaded_bills/` (not committed to git)

## Troubleshooting

### Script Exits with "Email already sent"

✅ This is expected behavior - prevents duplicate emails. Delete the row from `sent_emails.csv` to resend.

### "Failed to retrieve gas/trash bill data"

- Check your utility portal credentials in `.env`
- Verify your internet connection
- Utility websites may have changed their HTML structure (requires code update)
- Check if ChromeDriver is properly installed

### Email not sending

- Verify `SENDER_EMAIL` and `SENDER_PASSWORD` in `.env`
- For Gmail: Ensure you're using an [App Password](https://support.google.com/accounts/answer/185833)
- Check SMTP settings match your email provider

### ChromeDriver issues

- Ensure Chrome browser is installed
- Update ChromeDriver to match your Chrome version
- On macOS: `brew upgrade chromedriver`

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Contributing

Pull requests welcome! Please ensure:
- Code follows existing patterns
- `.env` is never committed
- Add appropriate error handling
- Update README if adding new features

## Automation Tips

### Schedule Monthly Execution

Use cron (Linux/macOS) or Task Scheduler (Windows) to run automatically:

**Cron example** (runs 1st of each month at 9 AM):
```bash
0 9 1 * * cd /path/to/RentalBillAutomation && /path/to/venv/bin/python rentalemail.py >> logs/cron.log 2>&1
```

## Contact

For issues or questions, please open an issue on GitHub.
