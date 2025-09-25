# Azure Virtual Desktop (AVD) Deployment with SQL Analytics

A reference implementation of a secure, domain‑integrated **Azure Virtual Desktop** (AVD) environment enhanced with a lightweight **operational analytics** layer on **Azure Database for MySQL**. The goal is to demonstrate production support practices—monitoring, incident triage, capacity planning—using **SQL (CRUD queries)** and small **Python** jobs.

> Author: Prince Dungrani  
> License: MIT

---

## 🔎 Project Description

- Deploys an AVD environment integrated with **Active Directory Domain Services (AD DS)** and synchronized to **Entra ID** (Azure AD) via AD Connect.
- Implements **FSLogix** profile containers on **Azure Files**, **MSIX** application packaging, and **MFA/Conditional Access** for secure access.
- Adds an **operational datastore** using **Azure Database for MySQL – Flexible Server** to log session events and errors.
- Uses **SQL** for production triage (stale sessions, FSLogix mount failures, slow logons) and **Python** to generate daily rollups for capacity and reliability insights.

---

## 🧭 Architecture (High-Level)

```
+-------------------+       +-----------------+        +--------------------------+
| On-Prem / Admin   |       | Azure Hub/Spoke |        | Azure Database for MySQL |
| (Mgmt Jumpbox)    |       | VNets + NSGs    |        | (Operational Datastore)  |
+---------+---------+       +--------+--------+        +-----------+--------------+
          |                           |                             |
          | AD Connect (Sync)         |                             |
+---------v---------+                 |                 +-----------v-------------+
| AD DS (Domain     |<----------------+---------------->| Python Jobs (cron/func) |
| Controller)       |                                   | Ingest & Reports        |
+---------+---------+                                   +-----------+-------------+
          |                                                             |
          | Domain Join                                                 |
+---------v---------+       FSLogix + MSIX + RDP/MFA         +---------v---------+
| AVD Host Pool     | <-------------------------------------- | MySQL Tables      |
| (Win 11 MultiSess)|                                         | sessions, errors, |
| App Groups        |                                         | mounts, versions  |
+-------------------+                                         +-------------------+
```

---

## 🧰 Tech Stack

- **Azure**: AVD, Entra ID (Azure AD), AD DS, Azure Files, VNets/NSGs
- **Profiles & Apps**: FSLogix, MSIX
- **Data & Automation**: **Azure Database for MySQL**, **Python 3**
- **Security**: Conditional Access + MFA, RBAC, Private Endpoints
- **Ops**: ITIL‑aligned incident handling, runbooks

---

## 🗃️ Database Schema (MySQL)

```sql
-- Sessions observed on host pool
CREATE TABLE IF NOT EXISTS sessions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_upn VARCHAR(255) NOT NULL,
  host_name VARCHAR(128) NOT NULL,
  logon_time DATETIME NOT NULL,
  last_heartbeat DATETIME NOT NULL,
  state ENUM('Active','Disconnected','Orphaned') NOT NULL DEFAULT 'Active',
  gpo_time_ms INT DEFAULT NULL,
  profile_size_mb INT DEFAULT NULL,
  image_version VARCHAR(64) DEFAULT NULL,
  agent_version VARCHAR(64) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FSLogix mounts and failures
CREATE TABLE IF NOT EXISTS fslogix_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_upn VARCHAR(255) NOT NULL,
  host_name VARCHAR(128) NOT NULL,
  event_time DATETIME NOT NULL,
  event_type ENUM('MountSuccess','MountFailure') NOT NULL,
  error_code VARCHAR(32) DEFAULT NULL,
  vhd_path VARCHAR(512) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Application launch telemetry (optional)
CREATE TABLE IF NOT EXISTS app_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_upn VARCHAR(255) NOT NULL,
  app_name VARCHAR(255) NOT NULL,
  host_name VARCHAR(128) NOT NULL,
  launch_time DATETIME NOT NULL,
  duration_ms INT DEFAULT NULL,
  status ENUM('OK','ERROR') NOT NULL,
  error_code VARCHAR(32) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### CRUD Examples

```sql
-- C: Create
INSERT INTO sessions (user_upn, host_name, logon_time, last_heartbeat, state, gpo_time_ms, profile_size_mb)
VALUES ('user1@contoso.com', 'AVD-HP-01', NOW(), NOW(), 'Active', 42000, 820);

-- R: Read
-- Orphaned sessions (>15 min no heartbeat)
SELECT * FROM sessions
WHERE TIMESTAMPDIFF(MINUTE, last_heartbeat, NOW()) > 15 AND state <> 'Orphaned';

-- U: Update
UPDATE sessions
SET state = 'Orphaned'
WHERE TIMESTAMPDIFF(MINUTE, last_heartbeat, NOW()) > 15 AND state <> 'Orphaned';

-- D: Delete (old telemetry > 90 days)
DELETE FROM fslogix_events
WHERE event_time < (NOW() - INTERVAL 90 DAY);
```

---

## 🔍 Production Support Queries (Triage)

```sql
-- 1) Users with 3+ FSLogix mount failures in last 24h
SELECT user_upn, COUNT(*) AS failures_24h
FROM fslogix_events
WHERE event_type = 'MountFailure' AND event_time >= (NOW() - INTERVAL 1 DAY)
GROUP BY user_upn
HAVING COUNT(*) >= 3
ORDER BY failures_24h DESC;

-- 2) Slow logons (correlate with GPO time and profile size)
SELECT user_upn, host_name, gpo_time_ms, profile_size_mb, logon_time
FROM sessions
WHERE gpo_time_ms > 30000 OR profile_size_mb > 1024
ORDER BY gpo_time_ms DESC, profile_size_mb DESC;

-- 3) Image/agent version drift across hosts
SELECT host_name, image_version, agent_version, COUNT(*) AS sessions_seen
FROM sessions
GROUP BY host_name, image_version, agent_version
ORDER BY sessions_seen DESC;
```

---

## 🐍 Python Ingest & Daily Rollups (Example)

```python
# file: jobs/rollups.py
import os, datetime, mysql.connector as mysql

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "avd_user"),
    "password": os.getenv("DB_PASS", "change_me"),
    "database": os.getenv("DB_NAME", "avd_ops"),
}

def get_conn():
    return mysql.connect(**DB)

def rollup_peak_concurrency():
    q = """
    SELECT DATE(logon_time) as d, HOUR(logon_time) as h, COUNT(*) as concurrent
    FROM sessions
    GROUP BY d, h
    ORDER BY d DESC, h DESC;
    """
    with get_conn() as cx, cx.cursor(dictionary=True) as cur:
        cur.execute(q)
        return cur.fetchall()

def main():
    data = rollup_peak_concurrency()
    # You could write to a CSV, dashboard, or send an email/slack
    for row in data[:10]:
        print(row)

if __name__ == "__main__":
    main()
```

> Tip: Run the job on a schedule (cron, GitHub Actions, Azure Functions Timer) to export CSV reports or update a dashboard.

---

## 🧪 Validation Checklist

- ✅ Host pool deployed; session hosts domain‑joined and visible in AVD
- ✅ FSLogix profile mount & persistence verified
- ✅ RemoteApp + desktop connectivity validated (web & MSTSC)
- ✅ MFA/Conditional Access enforced
- ✅ MySQL tables created; sample records ingested
- ✅ SQL triage queries return expected rows
- ✅ Python rollup script runs and prints sample rollups

---

## 🔐 Security & Compliance

- Enforce **MFA** and **Conditional Access** for all AVD users and admins.  
- Use **private endpoints** for Azure Files and MySQL where possible.  
- Restrict DB credentials via Key Vault / environment variables.  
- Enable **MySQL backups** with **point‑in‑time restore (PITR)** and test recovery.

---

## 🧯 Runbook (Incident Triage)

1. **Identify**: Use SQL queries to find orphaned sessions, FSLogix failures, or version drift.  
2. **Contain**: Log off stale sessions; remount profiles; move users to healthy hosts.  
3. **Remediate**: Reimage agents or update image versions as needed; verify FSLogix storage.  
4. **Recover**: Confirm user reconnect, validate profile integrity, and document root cause.  
5. **Improve**: Create a KB entry; update automation or alerts to prevent recurrences.

---

## 🚀 Getting Started

```bash
# Clone
git clone https://github.com/<your-handle>/avd-sql-analytics.git
cd avd-sql-analytics

# (Optional) Python venv
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install MySQL driver
pip install mysql-connector-python

# Create schema locally for testing (adjust creds)
mysql -h localhost -u avd_user -p avd_ops < db/schema.sql

# Run sample rollup
python jobs/rollups.py
```

---

## 📂 Repository Structure

```
.
├── db/
│   └── schema.sql           # MySQL DDL (copy from README)
├── jobs/
│   └── rollups.py           # Example Python rollup
├── runbooks/
│   └── incident-triage.md   # Optional: detailed SOPs
└── README.md
```

---

## 🏷️ License

This project is licensed under the **MIT License**. See `LICENSE` for details.
