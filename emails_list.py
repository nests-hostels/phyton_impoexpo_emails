import mysql.connector
import re
import openpyxl
from openpyxl import load_workbook
from datetime import datetime, timedelta

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
    
    # List of fake/booking email domains to exclude
    fake_domains = [
        '@guest.booking.com',
        '@expediapartnercentral.com', 
        '@noemail.com',
        '@airbnb.com'
    ]
    
    # Check if email ends with any of the fake domains
    for domain in fake_domains:
        if email_lower.endswith(domain):
            return False
    
    return True

def parse_date(date_string):
    """
    Parse date from DD/MM/YYYY format to YYYY-MM-DD
    Returns formatted date string or None if invalid
    """
    if not date_string or not isinstance(date_string, str):
        return None
    
    try:
        # Parse DD/MM/YYYY format
        date_obj = datetime.strptime(date_string.strip(), "%d/%m/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        print(f"⚠️  Invalid date format: {date_string}")
        return None

def calculate_checkin_date(checkout_date_str, nights):
    """
    Calculate checkin date by subtracting nights from checkout date
    Returns checkin date string in YYYY-MM-DD format or None
    """
    if not checkout_date_str or not nights:
        return None
    
    try:
        # Parse checkout date
        checkout_date = datetime.strptime(checkout_date_str, "%Y-%m-%d")
        # Subtract nights to get checkin date
        checkin_date = checkout_date - timedelta(days=int(nights))
        return checkin_date.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        print(f"⚠️  Could not calculate checkin date from {checkout_date_str} and {nights} nights")
        return None

def connect_to_database():
    """
    Connect to MySQL database
    Returns database connection
    """
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            database='nests_emails',
            user='root',
            password='',
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        print("✅ Connected to MySQL database successfully!")
        return conn
    except mysql.connector.Error as e:
        print(f"❌ Error connecting to MySQL database: {e}")
        return None

def read_excel_file(filename):
    """
    Read the Excel file and extract guest data
    Returns list of tuples with all guest information
    """
    try:
        # Load the Excel file
        workbook = load_workbook(filename)
        sheet = workbook.active
        
        guests_data = []
        
        # Skip header row (row 1), start from row 2
        for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            # Excel columns mapping:
            # 0: Nombre (first_name)
            # 1: Apellido (last_name) 
            # 2: Correo electrónico (email)
            # 3: Teléfono (phone)
            # 6: Ciudad (city)
            # 7: País (country)
            # 9: Código postal (postal_code)
            # 11: Noches de estadía (nights for calculation)
            # 13: Última estadía (checkout date)
            
            first_name = str(row[0]).strip() if row[0] else ""
            last_name = str(row[1]).strip() if row[1] else ""
            email = str(row[2]).strip() if row[2] else ""
            phone = str(row[3]).strip() if row[3] else ""
            city = str(row[6]).strip() if row[6] else ""
            country = str(row[7]).strip() if row[7] else ""
            postal_code = str(row[9]).strip() if row[9] else ""
            nights = row[11] if row[11] else None
            last_stay = str(row[13]).strip() if row[13] else ""
            
            # Only add if we have at least a name and email
            if first_name and email:
                guests_data.append({
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone': phone,
                    'city': city,
                    'country': country,
                    'postal_code': postal_code,
                    'nights': nights,
                    'last_stay': last_stay,
                    'row_number': row_num
                })
        
        print(f"📖 Read {len(guests_data)} guest records from Excel file")
        return guests_data
        
    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found!")
        return []
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        return []

def process_and_save_guests(conn, guests_data):
    """
    Process guest data and save ALL entries to database (no filtering)
    """
    cursor = conn.cursor()
    
    total_processed = 0
    saved_count = 0
    booking_emails = 0
    invalid_emails = 0
    date_issues = 0
    duplicates_skipped = 0
    other_errors = 0
    
    print("\n🔄 Processing ALL guests (no filtering)...")
    print("-" * 80)
    
    for guest in guests_data:
        total_processed += 1
        
        # Check email quality for reporting (but don't filter)
        is_valid_email_format = is_valid_email(guest['email'])
        is_booking_email = not is_not_booking_email(guest['email'])
        
        if not is_valid_email_format:
            invalid_emails += 1
        
        if is_booking_email:
            booking_emails += 1
        
        # Process dates
        checkout_date = parse_date(guest['last_stay'])
        checkin_date = None
        
        if checkout_date and guest['nights']:
            checkin_date = calculate_checkin_date(checkout_date, guest['nights'])
        
        if not checkout_date:
            date_issues += 1
        
        # Save ALL records to database (no filtering)
        try:
            insert_query = """
                INSERT INTO email_lists_2 
                (first_name, last_name, email, phone, checkin, checkout, country, city, postal_code, consent, hostel, created_at, updated_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """
            
            values = (
                guest['first_name'],
                guest['last_name'], 
                guest['email'],
                guest['phone'],
                checkin_date,
                checkout_date,
                guest['country'],
                guest['city'],
                guest['postal_code'] if guest['postal_code'] != 'None' else None,
                '1',  # consent = 1 (true)
                'Aguere'  # hostel name
            )
            
            cursor.execute(insert_query, values)
            saved_count += 1
            
            # Create status indicators for reporting
            status_flags = []
            if not is_valid_email_format:
                status_flags.append("📧❌")
            if is_booking_email:
                status_flags.append("🏨")
            if not checkout_date:
                status_flags.append("📅❌")
            
            status_text = " ".join(status_flags) if status_flags else "✅"
            
            # Show dates info
            date_info = ""
            if checkin_date and checkout_date:
                date_info = f" | {checkin_date} to {checkout_date}"
            elif checkout_date:
                date_info = f" | checkout: {checkout_date}"
            else:
                date_info = " | no dates"
            
            print(f"{status_text} Row {guest['row_number']}: {guest['first_name']} {guest['last_name']} - {guest['email']}{date_info}")
            
        except mysql.connector.IntegrityError as e:
            if "Duplicate entry" in str(e):
                duplicates_skipped += 1
                print(f"⚠️  Row {guest['row_number']}: Duplicate email skipped: {guest['email']}")
            else:
                other_errors += 1
                print(f"❌ Row {guest['row_number']}: Database error: {e}")
        except Exception as e:
            other_errors += 1
            print(f"❌ Row {guest['row_number']}: Unexpected error: {e}")
    
    # Save all changes to database
    conn.commit()
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 PROCESSING SUMMARY (ALL RECORDS SAVED):")
    print("=" * 80)
    print(f"Total records processed: {total_processed}")
    print(f"✅ Records saved to database: {saved_count}")
    print(f"⚠️  Duplicate emails skipped: {duplicates_skipped}")
    print(f"❌ Other errors: {other_errors}")
    print()
    print("📊 DATA QUALITY REPORT:")
    print(f"📧❌ Invalid email formats: {invalid_emails}")
    print(f"🏨 Booking.com emails: {booking_emails}")
    print(f"📅❌ Date parsing issues: {date_issues}")
    print("=" * 80)
    print("Legend: 📧❌=Invalid Email | 🏨=Booking.com | 📅❌=Date Issue | ✅=Clean Record")

def show_database_contents(conn, limit=10):
    """
    Display some saved records from the database
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM email_lists_2")
    total = cursor.fetchone()[0]
    
    print(f"\n📊 Database now contains {total} guest records in email_lists_2 table")
    
    if total > 0:
        print(f"\nFirst {min(limit, total)} records:")
        print("-" * 100)
        cursor.execute("""
            SELECT first_name, last_name, email, city, country, checkin, checkout 
            FROM email_lists_2 
            ORDER BY id DESC 
            LIMIT %s
        """, (limit,))
        
        for row in cursor.fetchall():
            dates = f"{row[5]} to {row[6]}" if row[5] and row[6] else "No dates"
            location = f"{row[3]}, {row[4]}" if row[3] and row[4] else "No location"
            print(f"{row[0]} {row[1]} - {row[2]} | {location} | {dates}")

def main():
    """
    Main function to run the entire extraction process
    """
    print("🏨 GUEST EMAIL EXTRACTOR FOR AGUERE HOSTEL")
    print("=" * 60)
    
    # Configuration
    excel_filename = "guests.xlsx"  # Your Excel file name
    
    # Step 1: Connect to database
    print("1. Connecting to MySQL database...")
    conn = connect_to_database()
    if not conn:
        print("❌ Could not connect to database. Exiting.")
        return
    
    # Step 2: Read Excel file
    print("\n2. Reading Excel file...")
    guests_data = read_excel_file(excel_filename)
    
    if not guests_data:
        print("❌ No data found. Exiting.")
        conn.close()
        return
    
    # Step 3: Process and save data
    print("\n3. Processing and filtering data...")
    process_and_save_guests(conn, guests_data)
    
    # Step 4: Show results
    print("\n4. Showing latest results...")
    show_database_contents(conn, limit=10)
    
    # Close database connection
    conn.close()
    
    print(f"\n🎉 Process completed! Check your 'email_lists_2' table in 'nests_emails' database.")
    print("Note: All records have hostel='Aguere' and consent='1'")

# Run the script
if __name__ == "__main__":
    main()