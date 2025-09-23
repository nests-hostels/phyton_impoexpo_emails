import mysql.connector
import re
from collections import Counter, defaultdict
from datetime import datetime
import logging
import os

# ======================================================================
# 🔧 CONFIGURATION SECTION
# ======================================================================

CONFIG = {
    'DATABASE': {
        'host': '127.0.0.1',
        'database': 'nests_emails',
        'table': 'email_lists_2',
        'user': 'root',
        'password': '',
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci'
    },
    
    'ANALYSIS': {
        'show_examples': 5,  # Number of example emails to show per domain
        'min_domain_count': 2  # Minimum emails per domain to show in detailed view
    },
    
    'LOGGING': {
        'log_directory': 'logs',
        'log_level': logging.INFO
    }
}

# ======================================================================

def setup_logging():
    """Setup logging"""
    log_dir = CONFIG['LOGGING']['log_directory']
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/database_analysis_{timestamp}.log"
    
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
    """Print to console and log to file"""
    print(message)
    logging.info(message)

def connect_to_database():
    """Connect to MySQL database"""
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

def fetch_all_emails(conn):
    """Fetch all emails from the database"""
    cursor = conn.cursor()
    table_name = CONFIG['DATABASE']['table']
    
    try:
        query = f"SELECT id, email FROM {table_name} WHERE email IS NOT NULL ORDER BY id"
        cursor.execute(query)
        results = cursor.fetchall()
        
        log_and_print(f"📊 Fetched {len(results)} email records from '{table_name}' table")
        return results
        
    except mysql.connector.Error as e:
        log_and_print(f"❌ Error fetching emails: {e}")
        return []
    finally:
        cursor.close()

def analyze_duplicates(email_data):
    """Analyze email duplicates"""
    log_and_print("\n" + "=" * 60)
    log_and_print("🔍 DUPLICATE EMAIL ANALYSIS")
    log_and_print("=" * 60)
    
    # Count email occurrences
    email_counts = Counter()
    email_ids = defaultdict(list)
    
    for email_id, email in email_data:
        email_lower = email.lower().strip()
        email_counts[email_lower] += 1
        email_ids[email_lower].append(email_id)
    
    # Find duplicates
    duplicates = {email: count for email, count in email_counts.items() if count > 1}
    
    if not duplicates:
        log_and_print("✅ No duplicate emails found!")
        return
    
    log_and_print(f"❌ Found {len(duplicates)} duplicate emails:")
    log_and_print(f"📊 Total duplicate records: {sum(duplicates.values()) - len(duplicates)}")
    log_and_print("")
    
    # Show duplicates sorted by count
    sorted_duplicates = sorted(duplicates.items(), key=lambda x: x[1], reverse=True)
    
    for email, count in sorted_duplicates[:20]:  # Show top 20
        ids = email_ids[email]
        log_and_print(f"📧 {email} - {count} times (IDs: {', '.join(map(str, ids))})")
    
    if len(duplicates) > 20:
        log_and_print(f"... and {len(duplicates) - 20} more duplicates")
    
    # SQL to remove duplicates (keep lowest ID)
    log_and_print("\n💡 SQL to remove duplicates (keep record with lowest ID):")
    log_and_print("DELETE t1 FROM email_lists_2 t1")
    log_and_print("INNER JOIN email_lists_2 t2") 
    log_and_print("WHERE t1.id > t2.id AND t1.email = t2.email;")

def extract_domain_info(email):
    """Extract domain and extension from email"""
    if not email or '@' not in email:
        return None, None
    
    try:
        domain_part = email.split('@')[1].lower().strip()
        if '.' in domain_part:
            extension = domain_part.split('.')[-1]
            return domain_part, extension
        else:
            return domain_part, domain_part  # Single word domain
    except:
        return None, None

def analyze_domains_and_extensions(email_data):
    """Analyze email domains and extensions"""
    log_and_print("\n" + "=" * 60)
    log_and_print("🌐 DOMAIN AND EXTENSION ANALYSIS")
    log_and_print("=" * 60)
    
    domains = Counter()
    extensions = Counter()
    domain_examples = defaultdict(list)
    
    invalid_emails = []
    
    for email_id, email in email_data:
        domain, extension = extract_domain_info(email)
        
        if domain is None:
            invalid_emails.append(email)
            continue
            
        domains[domain] += 1
        extensions[extension] += 1
        
        # Store examples (limit to avoid memory issues)
        if len(domain_examples[domain]) < CONFIG['ANALYSIS']['show_examples']:
            domain_examples[domain].append(email)
    
    # Show extensions summary
    log_and_print("📊 TOP EMAIL EXTENSIONS:")
    log_and_print("-" * 40)
    for ext, count in extensions.most_common(15):
        percentage = (count / len(email_data)) * 100
        log_and_print(f".{ext:<10} {count:>6} emails ({percentage:>5.1f}%)")
    
    # Show domain summary
    log_and_print(f"\n📊 TOP EMAIL DOMAINS (showing domains with {CONFIG['ANALYSIS']['min_domain_count']}+ emails):")
    log_and_print("-" * 80)
    
    for domain, count in domains.most_common(50):
        if count >= CONFIG['ANALYSIS']['min_domain_count']:
            percentage = (count / len(email_data)) * 100
            examples = ', '.join(domain_examples[domain][:3])
            log_and_print(f"{domain:<35} {count:>6} emails ({percentage:>5.1f}%) - Examples: {examples}")
    
    # Show suspicious domains
    log_and_print("\n🚨 POTENTIALLY SUSPICIOUS DOMAINS:")
    log_and_print("-" * 50)
    
    suspicious_keywords = ['guest', 'booking', 'noemail', 'temp', 'fake', 'test', 'example']
    suspicious_domains = []
    
    for domain, count in domains.items():
        domain_lower = domain.lower()
        if any(keyword in domain_lower for keyword in suspicious_keywords):
            suspicious_domains.append((domain, count))
    
    if suspicious_domains:
        for domain, count in sorted(suspicious_domains, key=lambda x: x[1], reverse=True):
            log_and_print(f"🚩 {domain:<35} {count:>6} emails")
    else:
        log_and_print("✅ No obviously suspicious domains found")
    
    # Show invalid emails
    if invalid_emails:
        log_and_print(f"\n❌ INVALID EMAIL FORMATS ({len(invalid_emails)} found):")
        log_and_print("-" * 50)
        for email in invalid_emails[:10]:
            log_and_print(f"❌ {email}")
        if len(invalid_emails) > 10:
            log_and_print(f"... and {len(invalid_emails) - 10} more invalid emails")

def generate_filter_suggestions(email_data):
    """Generate suggestions for email filtering rules"""
    log_and_print("\n" + "=" * 60)
    log_and_print("💡 FILTER RULE SUGGESTIONS")
    log_and_print("=" * 60)
    
    domains = Counter()
    for email_id, email in email_data:
        domain, _ = extract_domain_info(email)
        if domain:
            domains[domain] += 1
    
    # Suggest fake domains to add to filter
    fake_indicators = ['guest.booking', 'expedia', 'noemail', 'airbnb', '.booking', 'temp', 'fake']
    suggested_filters = []
    
    log_and_print("🔧 SUGGESTED DOMAINS TO ADD TO FAKE_DOMAINS CONFIG:")
    log_and_print("-" * 55)
    
    for domain, count in domains.most_common():
        domain_lower = domain.lower()
        if any(indicator in domain_lower for indicator in fake_indicators):
            suggested_filters.append(f"'@{domain}'")
            log_and_print(f"🚩 @{domain:<40} ({count} emails)")
    
    if suggested_filters:
        log_and_print("\n📝 Copy this to your CONFIG:")
        log_and_print("'fake_domains': [")
        for filter_rule in suggested_filters:
            log_and_print(f"    {filter_rule},")
        log_and_print("]")
    else:
        log_and_print("✅ No obvious fake domains detected beyond current filters")

def show_statistics_summary(email_data):
    """Show overall statistics"""
    log_and_print("\n" + "=" * 60)
    log_and_print("📊 OVERALL STATISTICS SUMMARY")
    log_and_print("=" * 60)
    
    total_emails = len(email_data)
    unique_emails = len(set(email.lower().strip() for _, email in email_data))
    duplicates = total_emails - unique_emails
    
    # Count valid emails
    valid_emails = 0
    for _, email in email_data:
        if '@' in email and '.' in email.split('@')[-1]:
            valid_emails += 1
    
    log_and_print(f"📧 Total email records: {total_emails}")
    log_and_print(f"✅ Unique emails: {unique_emails}")
    log_and_print(f"🔄 Duplicate emails: {duplicates}")
    log_and_print(f"✅ Valid format emails: {valid_emails}")
    log_and_print(f"❌ Invalid format emails: {total_emails - valid_emails}")
    
    if total_emails > 0:
        unique_percentage = (unique_emails / total_emails) * 100
        valid_percentage = (valid_emails / total_emails) * 100
        log_and_print(f"📊 Uniqueness rate: {unique_percentage:.1f}%")
        log_and_print(f"📊 Valid format rate: {valid_percentage:.1f}%")

def main():
    """Main function to run database analysis"""
    log_filename = setup_logging()
    
    log_and_print("🔍 DATABASE EMAIL ANALYZER")
    log_and_print("=" * 60)
    log_and_print(f"📄 Log file: {log_filename}")
    log_and_print(f"📊 Analyzing: {CONFIG['DATABASE']['database']}.{CONFIG['DATABASE']['table']}")
    log_and_print("=" * 60)
    
    # Connect to database
    conn = connect_to_database()
    if not conn:
        log_and_print("❌ Could not connect to database. Exiting.")
        return
    
    # Fetch all emails
    email_data = fetch_all_emails(conn)
    if not email_data:
        log_and_print("❌ No email data found. Exiting.")
        conn.close()
        return
    
    # Run all analyses
    show_statistics_summary(email_data)
    analyze_duplicates(email_data)
    analyze_domains_and_extensions(email_data)
    generate_filter_suggestions(email_data)
    
    # Close connection
    conn.close()
    
    log_and_print(f"\n🎉 Analysis completed!")
    log_and_print(f"📄 Full analysis saved to: {log_filename}")

if __name__ == "__main__":
    main()