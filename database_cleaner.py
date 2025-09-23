import mysql.connector
from datetime import datetime
import logging
import os
from collections import defaultdict

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
    
    'CLEANUP': {
        'create_backup': True,  # Create backup table before deletion
        'batch_size': 1000,     # Delete in batches to avoid locks
        'dry_run': True         # Set to True to see what would be deleted without actually deleting
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
    log_filename = f"{log_dir}/duplicate_cleanup_{timestamp}.log"
    
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

def get_table_stats(conn):
    """Get current table statistics"""
    cursor = conn.cursor()
    table_name = CONFIG['DATABASE']['table']
    
    try:
        # Total records
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_records = cursor.fetchone()[0]
        
        # Records with email
        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE email IS NOT NULL")
        records_with_email = cursor.fetchone()[0]
        
        # Unique emails
        cursor.execute(f"SELECT COUNT(DISTINCT LOWER(TRIM(email))) FROM {table_name} WHERE email IS NOT NULL")
        unique_emails = cursor.fetchone()[0]
        
        duplicates = records_with_email - unique_emails
        
        return {
            'total_records': total_records,
            'records_with_email': records_with_email,
            'unique_emails': unique_emails,
            'duplicates': duplicates
        }
        
    except mysql.connector.Error as e:
        log_and_print(f"❌ Error getting table stats: {e}")
        return None
    finally:
        cursor.close()

def create_backup_table(conn):
    """Create backup table before cleanup"""
    if not CONFIG['CLEANUP']['create_backup']:
        return True
    
    cursor = conn.cursor()
    table_name = CONFIG['DATABASE']['table']
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_table = f"{table_name}_backup_{timestamp}"
    
    try:
        log_and_print(f"📁 Creating backup table: {backup_table}")
        cursor.execute(f"CREATE TABLE {backup_table} LIKE {table_name}")
        cursor.execute(f"INSERT INTO {backup_table} SELECT * FROM {table_name}")
        
        # Get backup count
        cursor.execute(f"SELECT COUNT(*) FROM {backup_table}")
        backup_count = cursor.fetchone()[0]
        
        log_and_print(f"✅ Backup created successfully: {backup_count} records in {backup_table}")
        return backup_table
        
    except mysql.connector.Error as e:
        log_and_print(f"❌ Error creating backup: {e}")
        return None
    finally:
        cursor.close()

def find_duplicates(conn):
    """Find all duplicate email records"""
    cursor = conn.cursor()
    table_name = CONFIG['DATABASE']['table']
    
    try:
        log_and_print("🔍 Finding duplicate emails...")
        
        # Find all emails with their IDs, ordered by ID (keep lowest ID)
        query = f"""
            SELECT id, LOWER(TRIM(email)) as email_clean, email as original_email
            FROM {table_name} 
            WHERE email IS NOT NULL 
            ORDER BY id
        """
        
        cursor.execute(query)
        all_records = cursor.fetchall()
        
        # Group by email
        email_groups = defaultdict(list)
        for record_id, email_clean, original_email in all_records:
            email_groups[email_clean].append((record_id, original_email))
        
        # Find duplicates (groups with more than 1 record)
        duplicates_to_delete = []
        
        for email_clean, records in email_groups.items():
            if len(records) > 1:
                # Keep the first record (lowest ID), mark others for deletion
                keep_record = records[0]  # Lowest ID
                delete_records = records[1:]  # All others
                
                log_and_print(f"📧 {email_clean}: {len(records)} copies - Keep ID {keep_record[0]}, Delete IDs {[r[0] for r in delete_records]}")
                
                for record_id, original_email in delete_records:
                    duplicates_to_delete.append(record_id)
        
        log_and_print(f"📊 Found {len(duplicates_to_delete)} duplicate records to delete")
        return duplicates_to_delete
        
    except mysql.connector.Error as e:
        log_and_print(f"❌ Error finding duplicates: {e}")
        return []
    finally:
        cursor.close()

def delete_duplicates(conn, duplicate_ids):
    """Delete duplicate records in batches"""
    if not duplicate_ids:
        log_and_print("✅ No duplicates to delete!")
        return True
    
    if CONFIG['CLEANUP']['dry_run']:
        log_and_print(f"🔍 DRY RUN: Would delete {len(duplicate_ids)} duplicate records")
        log_and_print(f"🔍 IDs to delete: {duplicate_ids[:20]}..." if len(duplicate_ids) > 20 else f"🔍 IDs to delete: {duplicate_ids}")
        return True
    
    cursor = conn.cursor()
    table_name = CONFIG['DATABASE']['table']
    batch_size = CONFIG['CLEANUP']['batch_size']
    
    try:
        log_and_print(f"🗑️  Deleting {len(duplicate_ids)} duplicate records in batches of {batch_size}...")
        
        total_deleted = 0
        
        # Delete in batches
        for i in range(0, len(duplicate_ids), batch_size):
            batch = duplicate_ids[i:i + batch_size]
            placeholders = ','.join(['%s'] * len(batch))
            
            delete_query = f"DELETE FROM {table_name} WHERE id IN ({placeholders})"
            cursor.execute(delete_query, batch)
            
            deleted_count = cursor.rowcount
            total_deleted += deleted_count
            
            log_and_print(f"🗑️  Batch {i//batch_size + 1}: Deleted {deleted_count} records")
        
        # Commit all changes
        conn.commit()
        
        log_and_print(f"✅ Successfully deleted {total_deleted} duplicate records")
        return True
        
    except mysql.connector.Error as e:
        log_and_print(f"❌ Error deleting duplicates: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def main():
    """Main function to clean duplicates"""
    log_filename = setup_logging()
    
    dry_run_text = " (DRY RUN MODE)" if CONFIG['CLEANUP']['dry_run'] else ""
    
    log_and_print(f"🧹 DATABASE DUPLICATE CLEANER{dry_run_text}")
    log_and_print("=" * 60)
    log_and_print(f"📄 Log file: {log_filename}")
    log_and_print(f"📊 Target: {CONFIG['DATABASE']['database']}.{CONFIG['DATABASE']['table']}")
    log_and_print(f"📁 Backup: {'Enabled' if CONFIG['CLEANUP']['create_backup'] else 'Disabled'}")
    log_and_print(f"🔍 Dry run: {'Enabled' if CONFIG['CLEANUP']['dry_run'] else 'Disabled'}")
    log_and_print("=" * 60)
    
    # Connect to database
    conn = connect_to_database()
    if not conn:
        log_and_print("❌ Could not connect to database. Exiting.")
        return
    
    # Get initial statistics
    log_and_print("\n1. Getting initial statistics...")
    initial_stats = get_table_stats(conn)
    if not initial_stats:
        log_and_print("❌ Could not get table statistics. Exiting.")
        conn.close()
        return
    
    log_and_print(f"📊 Total records: {initial_stats['total_records']}")
    log_and_print(f"📧 Records with email: {initial_stats['records_with_email']}")
    log_and_print(f"✅ Unique emails: {initial_stats['unique_emails']}")
    log_and_print(f"🔄 Duplicate emails: {initial_stats['duplicates']}")
    
    if initial_stats['duplicates'] == 0:
        log_and_print("✅ No duplicates found! Nothing to clean.")
        conn.close()
        return
    
    # Create backup
    if not CONFIG['CLEANUP']['dry_run']:
        log_and_print("\n2. Creating backup...")
        backup_table = create_backup_table(conn)
        if not backup_table:
            log_and_print("❌ Backup failed. Aborting cleanup for safety.")
            conn.close()
            return
    else:
        log_and_print("\n2. Skipping backup (dry run mode)")
    
    # Find duplicates
    log_and_print("\n3. Finding duplicate records...")
    duplicate_ids = find_duplicates(conn)
    
    # Delete duplicates
    log_and_print("\n4. Deleting duplicates...")
    success = delete_duplicates(conn, duplicate_ids)
    
    if not success:
        log_and_print("❌ Duplicate deletion failed.")
        conn.close()
        return
    
    # Get final statistics
    if not CONFIG['CLEANUP']['dry_run']:
        log_and_print("\n5. Getting final statistics...")
        final_stats = get_table_stats(conn)
        
        log_and_print("\n" + "=" * 60)
        log_and_print("📊 CLEANUP SUMMARY")
        log_and_print("=" * 60)
        log_and_print(f"📊 Records before: {initial_stats['records_with_email']}")
        log_and_print(f"📊 Records after: {final_stats['records_with_email']}")
        log_and_print(f"🗑️  Records deleted: {initial_stats['records_with_email'] - final_stats['records_with_email']}")
        log_and_print(f"✅ Unique emails: {final_stats['unique_emails']}")
        log_and_print(f"🔄 Remaining duplicates: {final_stats['duplicates']}")
        log_and_print("=" * 60)
        
        if final_stats['duplicates'] == 0:
            log_and_print("🎉 All duplicates successfully removed!")
        else:
            log_and_print("⚠️  Some duplicates may remain - check logs for details")
    
    # Close connection
    conn.close()
    
    log_and_print(f"\n🎉 Cleanup completed!")
    log_and_print(f"📄 Full log saved to: {log_filename}")

if __name__ == "__main__":
    main()