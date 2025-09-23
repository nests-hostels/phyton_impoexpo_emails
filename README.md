# 🏨 Guest Email Management System

Sistema completo per la gestione e migrazione delle email degli ospiti tra Excel, Database MySQL e Brevo.

## 📋 Panoramica

Questo progetto consiste in due script Python che automatizzano la gestione delle email degli ospiti:

1. **📥 Import Script** (`extract_guests.py`) - Excel → Database MySQL
2. **📤 Export Script** (`brevo_export.py`) - Database MySQL → CSV per Brevo

## 🔧 Requisiti di Sistema

### Software Richiesto
- **Python 3.7+**
- **MySQL/MariaDB Server**
- **Accesso a phpMyAdmin** (opzionale, per gestione database)

### Librerie Python
```bash
pip install mysql-connector-python openpyxl
```

## 📁 Struttura del Progetto

```
project/
├── extract_guests.py          # Script import Excel → DB
├── brevo_export.py           # Script export DB → Brevo CSV
├── guests.xlsx               # File Excel di input
├── logs/                     # Directory log automatici
│   ├── guest_extraction_*.log
│   └── brevo_export_*.log
└── exports/                  # Directory export CSV
    └── brevo_export_*.csv
```

## 🗄️ Setup Database

### 1. Creare la Tabella Principale

```sql
CREATE TABLE `email_lists_2` (
  `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `first_name` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `checkin` date DEFAULT NULL,
  `checkout` date DEFAULT NULL,
  `country` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `city` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `postal_code` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `consent` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hostel` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2. Aggiungere Campi Opzionali (se necessari)

```sql
-- Campi aggiuntivi per statistiche complete
ALTER TABLE `email_lists_2` ADD COLUMN `total_nights` int(11) DEFAULT NULL AFTER `postal_code`;
ALTER TABLE `email_lists_2` ADD COLUMN `total_bookings` int(11) DEFAULT NULL AFTER `total_nights`;
ALTER TABLE `email_lists_2` ADD COLUMN `total_revenue` decimal(10,2) DEFAULT NULL AFTER `total_bookings`;
ALTER TABLE `email_lists_2` ADD COLUMN `spanish_dni` varchar(191) DEFAULT NULL AFTER `total_revenue`;
```

## 📥 Script 1: Import Excel → Database

### File: `extract_guests.py`

### ⚙️ Configurazione

Modifica la sezione `CONFIG` in cima al file:

```python
CONFIG = {
    'DATABASE': {
        'host': '127.0.0.1',           # Il tuo host MySQL
        'database': 'nests_emails',     # Nome del tuo database
        'table': 'email_lists_2',      # Nome della tabella
        'user': 'root',                # Username MySQL
        'password': '',                # Password MySQL
    },
    
    'APPLICATION': {
        'hostel_name': 'Aguere',       # Nome del tuo hostel
        'excel_filename': 'guests.xlsx', # Nome file Excel
        'consent_default': '1',         # Consenso default
    },
    
    'EMAIL_FILTERING': {
        'fake_domains': [               # Domini da marcare (non filtrare)
            '@guest.booking.com',
            '@expediapartnercentral.com', 
            '@noemail.com',
            '@airbnb.com'
        ]
    }
}
```

### 📊 Mapping Colonne Excel

Il file Excel deve avere queste colonne (posizioni configurabili in `EXCEL_COLUMNS`):

| Posizione | Nome Colonna | Campo Database |
|-----------|--------------|----------------|
| 0 | Nombre | first_name |
| 1 | Apellido | last_name |
| 2 | Correo electrónico | email |
| 3 | Teléfono | phone |
| 6 | Ciudad | city |
| 7 | País | country |
| 9 | Código postal | postal_code |
| 11 | Noches de estadía | (per calcolare checkin) |
| 13 | Última estadía | checkout |

### 🚀 Utilizzo

```bash
python extract_guests.py
```

### 📊 Output Atteso

```
🏨 GUEST EMAIL EXTRACTOR FOR AGUERE HOSTEL
================================================================
📄 Log file: logs/guest_extraction_20250923_143045.log
🏨 Hostel: Aguere
📊 Database: nests_emails.email_lists_2
📧 Filtering 4 fake domain types
================================================================

1. Connecting to MySQL database...
✅ Connected to MySQL database 'nests_emails' successfully!

2. Reading Excel file...
📖 Read 1489 guest records from Excel file 'guests.xlsx'

3. Processing and saving ALL data...
✅ Row 2: Romina Alejandra Sare - romysare@gmail.com | 2025-06-17 to 2025-06-18
🏨 Row 3: Pedro José Pérez - pperez.412223@guest.booking.com | 2025-10-08 to 2025-10-10
📅❌ Row 15: Luigi Verdi - luigi@gmail.com | no dates (SAVED ANYWAY)

📊 PROCESSING SUMMARY (ALL RECORDS SAVED):
================================================================
Total records processed: 1489
✅ Records saved to database: 1485
📅❌ Records saved WITHOUT dates: 234
⚠️  Duplicate emails skipped: 4

📊 DATA QUALITY REPORT:
📧❌ Invalid email formats: 23
🏨 Booking/Platform emails: 145
📅❌ Date parsing issues: 234
================================================================
```

## 📤 Script 2: Export Database → Brevo CSV

### File: `brevo_export.py`

### ⚙️ Configurazione

```python
CONFIG = {
    'DATABASE': {
        'host': '127.0.0.1',
        'database': 'nests_emails',
        'table': 'email_lists_2',      # Tabella sorgente
        'user': 'root',
        'password': '',
    },
    
    'EMAIL_FILTERING': {
        'fake_domains': [               # Domini da ESCLUDERE completamente
            '@guest.booking.com',
            '@expediapartnercentral.com', 
            '@noemail.com',
            '@airbnb.com'
        ]
    }
}
```

### 🗺️ Mapping Campi Brevo

| Campo CSV Brevo | Campo Database | Nota |
|-----------------|----------------|------|
| CONTACT ID | Generato automaticamente | 1, 2, 3... |
| EMAIL | email | ✅ Obbligatorio |
| FIRSTNAME | first_name | |
| LASTNAME | last_name | |
| SMS | phone | |
| LANDLINE_NUMBER | - | Sempre vuoto |
| WHATSAPP | - | Sempre vuoto |
| INTERESTS | - | Sempre vuoto |
| HOSTEL | hostel | Campo custom |
| POSTAL | postal_code | Campo custom |
| CITY | city | Campo custom |
| COUNTRY | country | Campo custom |
| CHECKIN | checkin | Campo custom (YYYY-MM-DD) |
| CHECKOUT | checkout | Campo custom (YYYY-MM-DD) |
| OPT-IN | consent | Campo custom |

### 🚀 Utilizzo

```bash
python brevo_export.py
```

### 📊 Output Atteso

```
📤 DATABASE TO BREVO CSV EXPORTER
================================================================
📄 Log file: logs/brevo_export_20250923_143045.log
📊 Source: nests_emails.email_lists_2
📧 Zero tolerance for invalid emails
🔧 Filtering 4 fake domain types
================================================================

1. Connecting to MySQL database...
✅ Connected to MySQL database 'nests_emails' successfully!

2. Fetching records from database...
📊 Fetched 1485 records from 'email_lists_2' table

3. Exporting valid emails to Brevo CSV...
✅ Row 1: Romina Alejandra Sare - romysare@gmail.com
❌ Row 15: Invalid email format skipped: not-valid-email
❌ Row 23: Booking/fake email skipped: guest@booking.com  
🔄 Row 45: Duplicate email skipped (exists in email_lists): mario@gmail.com

📊 BREVO EXPORT SUMMARY:
================================================================
Total records from database: 1485
✅ Valid emails exported: 1200
❌ Invalid email formats skipped: 45
❌ Booking/fake emails skipped: 156
🔄 Duplicate emails skipped: 89
📊 Total skipped: 290 emails

📁 CSV file created: exports/brevo_export_20250923_143045.csv
✅ Export success rate: 80.8%
================================================================
```

## 📁 File di Output

### 📝 Log Files

I log vengono salvati automaticamente in:
- `logs/guest_extraction_YYYYMMDD_HHMMSS.log` (import)
- `logs/brevo_export_YYYYMMDD_HHMMSS.log` (export)

### 📊 CSV Export per Brevo

Il file CSV viene creato in `exports/brevo_export_YYYYMMDD_HHMMSS.csv` con formato:

```csv
CONTACT ID,EMAIL,FIRSTNAME,LASTNAME,SMS,LANDLINE_NUMBER,WHATSAPP,INTERESTS,HOSTEL,POSTAL,CITY,COUNTRY,CHECKIN,CHECKOUT,OPT-IN
1,romysare@gmail.com,Romina Alejandra,Sare,647428264,,,Aguere,38683,Santa Cruz de Tenerife,España,2025-06-17,2025-06-18,1
2,gibbons.holly15@gmail.com,Holly,Gibbons,+44 7563 372992,,,Aguere,SE14 5NQ,New Cross,Reino Unido,2025-08-25,2025-08-29,1
```

## 🔧 Personalizzazioni Comuni

### 🏨 Cambiare Hostel

Modifica in entrambi gli script:
```python
'APPLICATION': {
    'hostel_name': 'NuovoHostel',
}
```

### 📧 Aggiungere Domini Fake

Aggiungi domini alla lista in entrambi gli script:
```python
'EMAIL_FILTERING': {
    'fake_domains': [
        '@guest.booking.com',
        '@expediapartnercentral.com', 
        '@noemail.com',
        '@airbnb.com',
        '@nuovo-dominio-fake.com'  # Nuovo dominio
    ]
}
```

### 🗄️ Cambiare Database/Tabella

Modifica in entrambi gli script:
```python
'DATABASE': {
    'host': 'nuovo-host.com',
    'database': 'nuovo_database',
    'table': 'nuova_tabella',
    'user': 'nuovo_user',
    'password': 'nuova_password'
}
```

### 🔄 Disattivare Controllo Duplicati

Nel file `brevo_export.py`, commenta queste righe:
```python
# if check_email_exists_in_original_table(conn, email):
#     duplicate_email_count += 1
#     log_and_print(f"❌ Row {contact_id}: Duplicate email skipped (exists in email_lists): {email}")
#     continue
```

## 🚨 Troubleshooting

### ❌ Errore: ModuleNotFoundError: No module named 'mysql'

**Soluzione:**
```bash
pip install mysql-connector-python openpyxl
```

### ❌ Errore: Access denied for user 'root'@'localhost'

**Soluzione:**
- Verifica username/password MySQL nel CONFIG
- Assicurati che MySQL sia avviato
- Verifica i permessi dell'utente

### ❌ Errore: Table 'email_lists_2' doesn't exist

**Soluzione:**
- Crea la tabella usando lo script SQL fornito sopra
- Verifica il nome del database e tabella nel CONFIG

### ❌ File Excel non trovato

**Soluzione:**
- Assicurati che `guests.xlsx` sia nella stessa cartella dello script
- Verifica il nome file nel CONFIG

### 📊 Molte email filtrate come "booking/fake"

**Normale:** I domini booking sono email temporanee create dalle piattaforme, non email reali degli ospiti.

### 📅 Molte date mancanti

**Normale:** Alcuni record potrebbero non avere date complete, ma vengono salvati comunque.

## 📈 Best Practices

### 🔄 Workflow Consigliato

1. **Backup database** prima dell'import
2. **Test con piccoli file** Excel prima di importare tutto
3. **Controllo log** dopo ogni operazione
4. **Verifica CSV** prima dell'upload a Brevo
5. **Mantenere copie** dei file di export

### 📊 Monitoraggio Qualità Dati

- **Success rate > 80%** = Buona qualità dati
- **Molti duplicati** = Possibile necessità di pulizia database
- **Molte email invalide** = Controllare sorgente dati Excel

### 🔐 Sicurezza

- **Non committare** le credenziali database nel codice
- **Usa file .env** per configurazioni sensibili (opzionale)
- **Backup regolari** del database

## 📞 Supporto

Per problemi tecnici:
1. **Controlla i log** generati automaticamente
2. **Verifica la configurazione** nel CONFIG
3. **Testa la connessione** database separatamente
4. **Controlla i permessi** file e cartelle

---

**🎉 Sistema pronto per la produzione!** 

Questi script gestiscono automaticamente migliaia di record con logging completo e gestione degli errori robusti.