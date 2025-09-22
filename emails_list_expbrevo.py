import mysql.connector
import csv
import re
from datetime import datetime
import logging
import os

# ======================================================================
# 🔧 CONFIGURATION SECTION - EDIT THESE VALUES AS NEEDED
# ======================================================================

CONFIG = {
    # Database Connection Settings
    'DATABASE': {
        'host': '127.0.0.1',
        'database': 'nests_emails',
        'table': 'email_lists_2',
        'user': 'root',
        'password': '',
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci'
    },
    
    # Export Settings
    'EXPORT': {
        'output_directory': 'exports',
        'filename_prefix': 'brevo_export',
        'csv_encoding': 'utf-8'
    },
    
    # Email Filtering Settings (ZERO TOLERANCE)
    'EMAIL_FILTERING': {
        'fake_domains': [
            '@guest.booking.com',
            '@expediapartnercentral.com', 
            '@noemail.com',
            '@airbnb.com'
        ]
    },
    
    # Logging Settings
    'LOGGING': {
        'log_directory': 'logs',
        'log_level': logging.INFO,
        'show_results_limit': 10
    },
    
    # Brevo CSV Field Mapping
    'BREVO_FIELDS': {
        'header': [
            'CONTACT ID', 'EMAIL', 'FIRSTNAME', 'LASTNAME', 'SMS', 
            'LANDLINE_NUMBER', 'WHATSAPP', 'INTERESTS', 
            'HOSTEL', 'POSTAL', 'CITY', 'COUNTRY', 'CHECKIN', 'CHECKOUT', 'OPT-IN'
        ],
        'database_mapping': {
            'EMAIL': 'email',
            'FIRSTNAME': 'first_name', 
            'LASTNAME': 'last_name',
            'SMS': 'phone',
            'HOSTEL': 'hostel',
            'POSTAL': 'postal_code',
            'CITY': 'city',
            'COUNTRY': 'country',
            'CHECKIN': 'checkin',
            'CHECKOUT': 'checkout',
            'OPT-IN': 'consent'
        }
    }
}

# ======================================================================
# 📋 END OF CONFIGURATION SECTION
# ======================================================================

def setup_logging():
    """
    Setup logging to both console and file with timestamp
    """
    # Create logs directory if it doesn't exist
    log_dir = CONFIG['LOGGING']['log_directory']
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/brevo_export_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=CONFIG['LOGGING']['log_level'],
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return log_filename

def log_and_print(message):
    """
    Print to console and log to file
    """
    print(message)
    logging.info(message)

def is_valid_email(email):
    """
    Check if email format is valid
    Returns True if email has correct format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    # Email pattern: something@domain.extension
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None

def is_not_booking_email(email):
    """
    Check if email is NOT from booking platforms or fake email services
    Returns True if email is real, False if it's from booking/fake services
    """
    if not email or not isinstance(email, str):
        return False
    
    email_lower = email.lower().strip()
    
    # Get fake domains from configuration
    fake_domains = CONFIG['EMAIL_FILTERING']['fake_domains']
    
    # Check if email ends with any of the fake domains
    for domain in fake_domains:
        if email_lower.endswith(domain):
            return False
    
    return True

def connect_to_database():
    """
    Connect to MySQL database using configuration settings
    Returns database connection
    """
    try:
        db_config = CONFIG['DATABASE']
        conn = mysql.connector.connect(
            host=db_config['host'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            charset=db_config['charset'],
            collation=db_config['collation']
        )
        log_and_print(f"✅ Connected to MySQL database '{db_config['database']}' successfully!")
        return conn
    except mysql.connector.Error as e:
        log_and_print(f"❌ Error connecting to MySQL database: {e}")
        return None

def fetch_all_records(conn):
    """
    Fetch all records from the database table
    Returns list of records as dictionaries
    """
    cursor = conn.cursor(dictionary=True)
    table_name = CONFIG['DATABASE']['table']
    
    try:
        # Select all records where email is not null
        query = f"SELECT * FROM {table_name} WHERE email IS NOT NULL ORDER BY id"
        cursor.execute(query)
        records = cursor.fetchall()
        
        log_and_print(f"📊 Fetched {len(records)} records from '{table_name}' table")
        return records
        
    except mysql.connector.Error as e:
        log_and_print(f"❌ Error fetching records: {e}")
        return []
    finally:
        cursor.close()

def format_date_for_brevo(date_value):
    """
    Format date for Brevo CSV (keep YYYY-MM-DD format)
    """
    if not date_value:
        return ""
    
    # If it's already a string in correct format, return as is
    if isinstance(date_value, str):
        return date_value.strip()
    
    # If it's a date object, format it
    try:
        return date_value.strftime("%Y-%m-%d")
    except:
        return ""

def create_csv_filename():
    """
    Create timestamped CSV filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = CONFIG['EXPORT']['output_directory']
    prefix = CONFIG['EXPORT']['filename_prefix']
    
    # Create export directory if it doesn't exist
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    
    return f"{export_dir}/{prefix}_{timestamp}.csv"

def export_to_brevo_csv(records):
    """
    Export records to Brevo-compatible CSV file
    Returns (csv_filename, stats)
    """
    csv_filename = create_csv_filename()
    
    total_records = len(records)
    exported_count = 0
    invalid_email_count = 0
    booking_email_count = 0
    
    log_and_print(f"\n🔄 Exporting to Brevo CSV: {csv_filename}")
    log_and_print("-" * 80)
    
    with open(csv_filename, 'w', newline='', encoding=CONFIG['EXPORT']['csv_encoding']) as csvfile:
        # Get headers and field mapping from config
        headers = CONFIG['BREVO_FIELDS']['header']
        field_mapping = CONFIG['BREVO_FIELDS']['database_mapping']
        
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(headers)
        log_and_print(f"📝 CSV Header: {', '.join(headers)}")
        
        contact_id = 1
        
        for record in records:
            email = record.get('email', '').strip() if record.get('email') else ''
            
            # ZERO TOLERANCE EMAIL VALIDATION
            if not is_valid_email(email):
                invalid_email_count += 1
                log_and_print(f"❌ Row {contact_id}: Invalid email format skipped: {email}")
                continue
            
            if not is_not_booking_email(email):
                booking_email_count += 1
                log_and_print(f"❌ Row {contact_id}: Booking/fake email skipped: {email}")
                continue
            
            # Create CSV row
            csv_row = []
            
            for header in headers:
                if header == 'CONTACT ID':
                    csv_row.append(contact_id)
                elif header in field_mapping:
                    # Get value from database record
                    db_field = field_mapping[header]
                    value = record.get(db_field, '')
                    
                    # Special formatting for dates
                    if header in ['CHECKIN', 'CHECKOUT']:
                        value = format_date_for_brevo(value)
                    
                    # Convert None to empty string
                    if value is None:
                        value = ''
                    
                    csv_row.append(str(value).strip())
                else:
                    # Fields not mapped (LANDLINE_NUMBER, WHATSAPP, INTERESTS)
                    csv_row.append('')
            
            # Write row to CSV
            writer.writerow(csv_row)
            exported_count += 1
            
            # Log every valid export
            log_and_print(f"✅ Row {contact_id}: {record.get('first_name', '')} {record.get('last_name', '')} - {email}")
            
            contact_id += 1
    
    # Statistics
    stats = {
        'total_records': total_records,
        'exported_count': exported_count,
        'invalid_email_count': invalid_email_count,
        'booking_email_count': booking_email_count,
        'csv_filename': csv_filename
    }
    
    return csv_filename, stats

def show_export_summary(stats):
    """
    Display export summary statistics
    """
    log_and_print("\n" + "=" * 80)
    log_and_print("📊 BREVO EXPORT SUMMARY:")
    log_and_print("=" * 80)
    log_and_print(f"Total records from database: {stats['total_records']}")
    log_and_print(f"✅ Valid emails exported: {stats['exported_count']}")
    log_and_print(f"❌ Invalid email formats skipped: {stats['invalid_email_count']}")
    log_and_print(f"❌ Booking/fake emails skipped: {stats['booking_email_count']}")
    log_and_print("")
    log_and_print(f"📁 CSV file created: {stats['csv_filename']}")
    log_and_print(f"🔧 Filtered domains: {', '.join(CONFIG['EMAIL_FILTERING']['fake_domains'])}")
    log_and_print("=" * 80)
    
    # Calculate success rate
    if stats['total_records'] > 0:
        success_rate = (stats['exported_count'] / stats['total_records']) * 100
        log_and_print(f"✅ Export success rate: {success_rate:.1f}%")

def main():
    """
    Main function to run the database to Brevo CSV export
    """
    # Setup logging first
    log_filename = setup_logging()
    
    log_and_print("📤 DATABASE TO BREVO CSV EXPORTER")
    log_and_print("=" * 60)
    log_and_print(f"📄 Log file: {log_filename}")
    log_and_print(f"📊 Source: {CONFIG['DATABASE']['database']}.{CONFIG['DATABASE']['table']}")
    log_and_print(f"📧 Zero tolerance for invalid emails")
    log_and_print(f"🔧 Filtering {len(CONFIG['EMAIL_FILTERING']['fake_domains'])} fake domain types")
    log_and_print("=" * 60)
    
    # Step 1: Connect to database
    log_and_print("1. Connecting to MySQL database...")
    conn = connect_to_database()
    if not conn:
        log_and_print("❌ Could not connect to database. Exiting.")
        return
    
    # Step 2: Fetch all records
    log_and_print("\n2. Fetching records from database...")
    records = fetch_all_records(conn)
    
    if not records:
        log_and_print("❌ No records found. Exiting.")
        conn.close()
        return
    
    # Step 3: Export to CSV
    log_and_print("\n3. Exporting valid emails to Brevo CSV...")
    csv_filename, stats = export_to_brevo_csv(records)
    
    # Step 4: Show results
    log_and_print("\n4. Export completed!")
    show_export_summary(stats)
    
    # Close database connection
    conn.close()
    
    log_and_print(f"\n🎉 Export completed successfully!")
    log_and_print(f"📁 Brevo CSV ready for import: {csv_filename}")
    log_and_print(f"📄 Complete log saved to: {log_filename}")

# Run the script
if __name__ == "__main__":
    main()