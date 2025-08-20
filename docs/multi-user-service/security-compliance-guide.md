# EMUSES Security and Compliance Guide

**Comprehensive security controls and compliance frameworks for enterprise EMUSES deployments**

## **Essential Security Overview**

EMUSES with Vault integration provides enterprise-grade security controls to meet regulatory requirements including SOC 2, HIPAA, GDPR, and industry security standards. This guide covers implementation of security controls and compliance frameworks.

### Security Architecture

| Security Layer | Technology | Compliance Benefit |
|----------------|------------|-------------------|
| **Secret Management** | HashiCorp Vault | Centralized secrets, audit trails |
| **Data Encryption** | AES-256, TLS 1.3 | Data protection at rest and transit |
| **Access Control** | RBAC, LDAP/SAML | Identity management, least privilege |
| **Audit Logging** | Vault audit, application logs | Compliance reporting, forensics |
| **Network Security** | VPC, firewalls, VPN | Network segmentation, secure access |

<details markdown="1">
<summary>🛡️ **Security Control Matrix**</summary>

Comprehensive security controls implementation:

| Control Family | NIST CSF | SOC 2 | HIPAA | Implementation |
|----------------|----------|-------|-------|----------------|
| **Identity & Access** | PR.AC | CC6.1-CC6.3 | 164.312(a) | Vault RBAC + LDAP |
| **Data Protection** | PR.DS | CC6.7 | 164.312(e) | AES-256 encryption |
| **Audit & Monitoring** | DE.AE | CC7.1-CC7.4 | 164.312(b) | Vault audit logs |
| **Incident Response** | RS.RP | CC7.4 | 164.308(a)(6) | Automated alerting |
| **Business Continuity** | RC.RP | CC9.1 | 164.308(a)(7) | Backup/DR procedures |

**Implementation Status**: All controls implemented with Vault integration

</details>

## **SOC 2 Type II Compliance**

### Trust Service Criteria Implementation

<details markdown="1">
<summary>🔐 **Security (CC1.1 - CC6.8)**</summary>

Implementation of SOC 2 security criteria:

**CC1.1 - Governance and Risk Management**:
```bash
# Document security policies and procedures
cat > security-policy.md << EOF
# EMUSES Security Policy

## Access Control Policy
- All users must authenticate via LDAP/SAML
- Multi-factor authentication required for admin access
- Role-based access control (RBAC) enforced

## Data Protection Policy
- All data encrypted at rest (AES-256)
- All data encrypted in transit (TLS 1.3)
- Regular security assessments conducted

## Incident Response Policy
- 24/7 security monitoring
- Automated alerting for security events
- Documented incident response procedures
EOF
```

**CC6.1 - Access Control**:
```bash
# Vault RBAC implementation
vault policy write emuses-admin - << EOF
# Admin access to all EMUSES secrets
path "secret/data/emuses/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Access to audit logs
path "sys/audit/*" {
  capabilities = ["read", "list"]
}
EOF

vault policy write emuses-user - << EOF
# User access to own data only
path "secret/data/emuses/users/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
EOF

# Assign policies to roles
vault write auth/ldap/groups/admins policies=emuses-admin
vault write auth/ldap/groups/users policies=emuses-user
```

**CC6.7 - Data Encryption**:
```bash
# Encryption at rest configuration
vault write transit/keys/emuses-data-key \
  type=aes256-gcm96 \
  derived=false \
  exportable=false

# Encryption in transit configuration
openssl req -x509 -newkey rsa:4096 \
  -keyout /etc/ssl/private/emuses.key \
  -out /etc/ssl/certs/emuses.crt \
  -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=emuses.company.com"

# Verify TLS configuration
openssl s_client -connect emuses.company.com:443 -tls1_3
```

**CC7.1 - System Monitoring**:
```bash
# Comprehensive monitoring setup
vault audit enable file file_path=/var/log/vault/audit.log

# Monitor critical security events
grep -E "(FAILED|DENIED|ERROR)" /var/log/vault/audit.log | \
  jq -r '{time: .time, operation: .request.operation, path: .request.path, error: .error}'

# Automated alerting
#!/bin/bash
# security-monitor.sh
FAILED_LOGINS=$(grep "FAILED" /var/log/vault/audit.log | wc -l)
if [ "$FAILED_LOGINS" -gt 10 ]; then
  echo "Security Alert: $FAILED_LOGINS failed login attempts" | \
    mail -s "EMUSES Security Alert" security@company.com
fi
```

</details>

<details markdown="1">
<summary>📊 **Availability (CC9.1)**</summary>

High availability and business continuity controls:

```bash
# Automated backup procedures
#!/bin/bash
# backup-script.sh

# Vault backup
vault operator raft snapshot save /backup/vault-$(date +%Y%m%d-%H%M%S).snap

# Database backup
pg_dump -h postgres.company.com -U emuses emuses_production > \
  /backup/emuses-db-$(date +%Y%m%d-%H%M%S).sql

# Model storage backup
aws s3 sync s3://emuses-models /backup/models/$(date +%Y%m%d)/

# Encrypt backups
gpg --encrypt --recipient backup@company.com /backup/*.snap
gpg --encrypt --recipient backup@company.com /backup/*.sql

# Test backup integrity
vault operator raft snapshot restore -check-only /backup/vault-latest.snap
```

**Recovery Time Objectives**:
- **RTO**: 4 hours for complete system recovery
- **RPO**: 1 hour maximum data loss
- **MTTR**: 30 minutes for application recovery

</details>

### SOC 2 Audit Preparation

<details markdown="1">
<summary>📋 **Audit Evidence Collection**</summary>

Automated evidence collection for SOC 2 audits:

```bash
#!/bin/bash
# soc2-evidence-collection.sh

AUDIT_DIR="/audit-evidence/$(date +%Y%m%d)"
mkdir -p "$AUDIT_DIR"

# CC6.1 - Access control evidence
echo "=== Access Control Evidence ===" > "$AUDIT_DIR/access-control.txt"
vault list auth/ldap/groups >> "$AUDIT_DIR/access-control.txt"
vault policy list >> "$AUDIT_DIR/access-control.txt"

# CC6.7 - Encryption evidence
echo "=== Encryption Evidence ===" > "$AUDIT_DIR/encryption.txt"
vault read transit/keys/emuses-data-key >> "$AUDIT_DIR/encryption.txt"
openssl x509 -in /etc/ssl/certs/emuses.crt -text >> "$AUDIT_DIR/encryption.txt"

# CC7.1 - Monitoring evidence
echo "=== Monitoring Evidence ===" > "$AUDIT_DIR/monitoring.txt"
vault read sys/audit >> "$AUDIT_DIR/monitoring.txt"
tail -100 /var/log/vault/audit.log >> "$AUDIT_DIR/monitoring.txt"

# CC9.1 - Availability evidence
echo "=== Availability Evidence ===" > "$AUDIT_DIR/availability.txt"
ls -la /backup/ >> "$AUDIT_DIR/availability.txt"
systemctl status emuses >> "$AUDIT_DIR/availability.txt"

# Generate evidence package
tar -czf "$AUDIT_DIR.tar.gz" "$AUDIT_DIR"
gpg --encrypt --recipient auditor@company.com "$AUDIT_DIR.tar.gz"
```

**Audit Timeline**: Quarterly evidence collection, annual Type II audit

</details>

## **HIPAA Compliance (Healthcare)**

### HIPAA Security Rule Implementation

<details markdown="1">
<summary>🏥 **Administrative Safeguards (164.308)**</summary>

HIPAA administrative controls implementation:

**164.308(a)(1) - Security Officer**:
```bash
# Designate security officer role
vault policy write hipaa-security-officer - << EOF
# Full access to security configurations
path "sys/auth/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

path "sys/audit/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

path "sys/policies/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
EOF

# Assign security officer
vault write auth/ldap/users/security-officer policies=hipaa-security-officer
```

**164.308(a)(3) - Workforce Training**:
```bash
# Security awareness tracking
cat > security-training.md << EOF
# HIPAA Security Training Record

## Required Training Modules
- [ ] PHI Handling Procedures
- [ ] Access Control Requirements
- [ ] Incident Reporting
- [ ] Password Management
- [ ] Vault Usage Guidelines

## Training Completion Tracking
User: ________________
Date: ________________
Trainer: ________________
Next Review: ________________
EOF
```

**164.308(a)(6) - Incident Response**:
```bash
# Automated incident detection
#!/bin/bash
# hipaa-incident-monitor.sh

# Monitor for unauthorized PHI access
UNAUTHORIZED_ACCESS=$(grep "DENIED.*phi" /var/log/vault/audit.log | wc -l)
if [ "$UNAUTHORIZED_ACCESS" -gt 0 ]; then
  echo "HIPAA INCIDENT: Unauthorized PHI access detected" | \
    mail -s "HIPAA Security Incident" privacy-officer@company.com
fi

# Monitor for data exports
DATA_EXPORTS=$(grep "export.*phi" /var/log/emuses/access.log | wc -l)
if [ "$DATA_EXPORTS" -gt 5 ]; then
  echo "HIPAA ALERT: Unusual PHI export activity" | \
    mail -s "HIPAA Data Activity Alert" privacy-officer@company.com
fi
```

</details>

<details markdown="1">
<summary>💾 **Physical and Technical Safeguards (164.310/164.312)**</summary>

Physical and technical security controls:

**164.310 - Physical Safeguards**:
```bash
# Data center security documentation
cat > physical-security.md << EOF
# Physical Security Controls

## Facility Access Controls (164.310(a)(1))
- Badge-controlled access to data center
- Security cameras with 90-day retention
- Visitor escort requirements
- Access logs maintained

## Workstation Controls (164.310(b))
- Encrypted endpoints required
- Screen locks after 15 minutes
- Physical device tracking
- Remote wipe capabilities

## Media Controls (164.310(d)(1))
- Encrypted storage media
- Secure disposal procedures
- Asset tracking system
- Chain of custody documentation
EOF
```

**164.312 - Technical Safeguards**:
```bash
# PHI encryption implementation
vault write transit/keys/phi-encryption-key \
  type=aes256-gcm96 \
  derived=false \
  exportable=false

# Audit controls
vault audit enable file \
  file_path=/var/log/hipaa/audit.log \
  log_raw=true

# Automatic logoff
cat > session-timeout.conf << EOF
# 15-minute session timeout
session.timeout=900
session.warning=60
EOF

# Unique user identification
vault write auth/ldap/config \
  url="ldap://ldap.company.com" \
  userdn="ou=users,dc=company,dc=com" \
  groupdn="ou=groups,dc=company,dc=com" \
  binddn="cn=vault,ou=service,dc=company,dc=com"
```

</details>

### HIPAA Audit Requirements

<details markdown="1">
<summary>📋 **Audit Trail Implementation**</summary>

Comprehensive audit logging for HIPAA compliance:

```bash
# HIPAA audit log configuration
vault audit enable file \
  file_path=/var/log/hipaa/vault-audit.log \
  log_raw=false \
  hmac_accessor=true \
  mode=0600

# Application-level PHI access logging
python_audit_logger = """
import logging
import json
from datetime import datetime

class HIPAAAuditLogger:
    def __init__(self):
        self.logger = logging.getLogger('hipaa_audit')
        handler = logging.FileHandler('/var/log/hipaa/phi-access.log')
        formatter = logging.Formatter('%(asctime)s %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_phi_access(self, user_id, patient_id, action, resource):
        audit_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'patient_id': patient_id,
            'action': action,
            'resource': resource,
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        }
        self.logger.info(json.dumps(audit_record))

# Usage in EMUSES application
audit = HIPAAAuditLogger()
audit.log_phi_access(
    user_id='user123',
    patient_id='patient456',
    action='view_model',
    resource='neuroimaging_model_789'
)
"""

# Audit report generation
python << EOF
import json
from datetime import datetime, timedelta

def generate_hipaa_audit_report(start_date, end_date):
    audit_events = []
    
    with open('/var/log/hipaa/phi-access.log', 'r') as f:
        for line in f:
            try:
                event = json.loads(line.split(' ', 1)[1])
                event_date = datetime.fromisoformat(event['timestamp'])
                
                if start_date <= event_date <= end_date:
                    audit_events.append(event)
            except:
                continue
    
    # Generate summary report
    report = {
        'period': f"{start_date} to {end_date}",
        'total_access_events': len(audit_events),
        'unique_users': len(set(e['user_id'] for e in audit_events)),
        'unique_patients': len(set(e['patient_id'] for e in audit_events)),
        'access_by_action': {}
    }
    
    for event in audit_events:
        action = event['action']
        report['access_by_action'][action] = report['access_by_action'].get(action, 0) + 1
    
    with open('/reports/hipaa-audit-report.json', 'w') as f:
        json.dump(report, f, indent=2)

# Generate monthly report
start = datetime.now().replace(day=1)
end = start + timedelta(days=32)
end = end.replace(day=1) - timedelta(days=1)
generate_hipaa_audit_report(start, end)
EOF
```

**Retention**: 6 years for audit logs, secure storage with encryption

</details>

## **GDPR Compliance (EU Data Protection)**

### GDPR Rights Implementation

<details markdown="1">
<summary>🇪🇺 **Data Subject Rights (Articles 15-22)**</summary>

Implementation of GDPR data subject rights:

**Article 15 - Right of Access**:
```bash
# Data export functionality
#!/bin/bash
# gdpr-data-export.sh

USER_EMAIL="$1"
EXPORT_DIR="/tmp/gdpr-export-$(date +%s)"
mkdir -p "$EXPORT_DIR"

# Export user data from EMUSES
python << EOF
import json
from emuses.multi_user_service.models import User
from emuses.multi_user_service.database import get_async_session

async def export_user_data(email):
    async with get_async_session() as session:
        user = await session.execute(
            select(User).where(User.email == email)
        )
        user = user.scalar_one_or_none()
        
        if user:
            user_data = {
                'personal_data': {
                    'email': user.email,
                    'organization': user.organization,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None
                },
                'usage_data': {
                    'models_created': len(user.models),
                    'jobs_executed': len(user.jobs),
                    'storage_used': user.storage_quota_used
                }
            }
            
            with open('$EXPORT_DIR/user-data.json', 'w') as f:
                json.dump(user_data, f, indent=2)

import asyncio
asyncio.run(export_user_data('$USER_EMAIL'))
EOF

# Encrypt export for user
gpg --encrypt --recipient "$USER_EMAIL" "$EXPORT_DIR/user-data.json"
```

**Article 17 - Right to Erasure**:
```bash
# Data deletion functionality
#!/bin/bash
# gdpr-data-deletion.sh

USER_EMAIL="$1"
DELETION_LOG="/var/log/gdpr/deletions.log"

# Log deletion request
echo "$(date): Deletion requested for $USER_EMAIL" >> "$DELETION_LOG"

# Delete user data from EMUSES
python << EOF
import asyncio
from emuses.multi_user_service.models import User
from emuses.multi_user_service.database import get_async_session

async def delete_user_data(email):
    async with get_async_session() as session:
        user = await session.execute(
            select(User).where(User.email == email)
        )
        user = user.scalar_one_or_none()
        
        if user:
            # Delete associated data
            # Note: Implement according to your data model
            await session.delete(user)
            await session.commit()
            print(f"User {email} data deleted successfully")

asyncio.run(delete_user_data('$USER_EMAIL'))
EOF

# Remove from Vault (if user-specific secrets exist)
vault kv delete secret/emuses/users/"$USER_EMAIL"

echo "$(date): Deletion completed for $USER_EMAIL" >> "$DELETION_LOG"
```

**Article 20 - Data Portability**:
```bash
# Standardized data export
#!/bin/bash
# gdpr-data-portability.sh

USER_EMAIL="$1"
EXPORT_FORMAT="${2:-json}"  # json, csv, xml

python << EOF
import json
import csv
import xml.etree.ElementTree as ET
from emuses.multi_user_service.models import User

def export_to_json(user_data):
    return json.dumps(user_data, indent=2)

def export_to_csv(user_data):
    # Flatten data for CSV export
    flattened = {}
    for category, data in user_data.items():
        if isinstance(data, dict):
            for key, value in data.items():
                flattened[f"{category}_{key}"] = value
        else:
            flattened[category] = data
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=flattened.keys())
    writer.writeheader()
    writer.writerow(flattened)
    return output.getvalue()

def export_to_xml(user_data):
    root = ET.Element("user_data")
    for category, data in user_data.items():
        category_elem = ET.SubElement(root, category)
        if isinstance(data, dict):
            for key, value in data.items():
                elem = ET.SubElement(category_elem, key)
                elem.text = str(value)
        else:
            category_elem.text = str(data)
    
    return ET.tostring(root, encoding='unicode')

# Export logic here...
EOF
```

</details>

<details markdown="1">
<summary>🔒 **Privacy by Design Implementation**</summary>

Technical and organizational measures for GDPR compliance:

```bash
# Data minimization policies
vault policy write gdpr-data-access - << EOF
# Restrict access to personal data
path "secret/data/emuses/users/*" {
  capabilities = ["read"]
  allowed_parameters = {
    "data" = ["processing_preferences", "consent_status"]
  }
  denied_parameters = {
    "data" = ["personal_identifiers", "sensitive_attributes"]
  }
}
EOF

# Consent management
python << EOF
class ConsentManager:
    def __init__(self):
        self.vault_client = hvac.Client()
    
    def record_consent(self, user_id, purpose, consent_given, timestamp):
        consent_record = {
            'user_id': user_id,
            'purpose': purpose,
            'consent_given': consent_given,
            'timestamp': timestamp,
            'withdrawal_method': 'email_privacy_officer'
        }
        
        self.vault_client.secrets.kv.v2.create_or_update_secret(
            path=f'gdpr/consent/{user_id}/{purpose}',
            secret=consent_record
        )
    
    def check_consent(self, user_id, purpose):
        try:
            response = self.vault_client.secrets.kv.v2.read_secret_version(
                path=f'gdpr/consent/{user_id}/{purpose}'
            )
            return response['data']['data']['consent_given']
        except:
            return False  # No consent recorded = no consent

# Usage
consent_mgr = ConsentManager()
consent_mgr.record_consent(
    user_id='user123',
    purpose='neuroimaging_analysis',
    consent_given=True,
    timestamp='2023-12-15T10:30:00Z'
)
EOF

# Data retention policies
cat > gdpr-retention-policy.md << EOF
# GDPR Data Retention Policy

## Personal Data Categories
- **Account Data**: Retained while account active + 30 days
- **Usage Logs**: Retained for 12 months
- **Audit Logs**: Retained for 7 years (legal requirement)
- **Research Data**: Retained per research consent (max 10 years)

## Automated Deletion
- Daily cleanup of expired data
- Quarterly review of retention compliance
- Annual data mapping updates

## Legal Basis Documentation
- Consent: Documented in Vault
- Legitimate Interest: Business justification documented
- Legal Obligation: Retention schedule documented
EOF
```

</details>

## **Additional Compliance Frameworks**

### PCI DSS (Payment Card Industry)

<details markdown="1">
<summary>💳 **PCI DSS Requirements (if applicable)**</summary>

Implementation for environments processing payment data:

```bash
# PCI DSS Requirement 3 - Protect stored cardholder data
vault write transit/keys/pci-encryption-key \
  type=aes256-gcm96 \
  derived=false \
  exportable=false

# PCI DSS Requirement 8 - Identity management
vault auth enable ldap
vault write auth/ldap/config \
  url="ldap://ldap.company.com" \
  userdn="ou=users,dc=company,dc=com" \
  groupdn="ou=groups,dc=company,dc=com"

# PCI DSS Requirement 10 - Network monitoring
vault audit enable file \
  file_path=/var/log/pci/vault-audit.log \
  mode=0600

# PCI DSS Requirement 11 - Security testing
#!/bin/bash
# pci-security-scan.sh
nmap -sS -O target.company.com
openvas-cli -h target.company.com
```

</details>

### FedRAMP (US Federal)

<details markdown="1">
<summary>🏛️ **FedRAMP Controls Implementation**</summary>

Federal security requirements implementation:

```bash
# AC-2 Account Management
vault auth enable userpass
vault policy write fedramp-user - << EOF
path "secret/data/emuses/users/{{identity.entity.name}}/*" {
  capabilities = ["create", "read", "update", "delete"]
}
EOF

# AU-2 Audit Events
vault audit enable file \
  file_path=/var/log/fedramp/audit.log \
  format=json \
  hmac_accessor=false

# SC-8 Transmission Confidentiality
openssl req -new -x509 -days 365 -nodes \
  -out /etc/ssl/certs/fedramp.crt \
  -keyout /etc/ssl/private/fedramp.key \
  -config fedramp-ssl.conf

# Configuration for FIPS 140-2 compliance
vault write sys/seal-config \
  type="awskms" \
  region="us-gov-west-1" \
  kms_key_id="alias/fedramp-vault-key"
```

</details>

## **Security Testing and Validation**

### Penetration Testing

<details markdown="1">
<summary>🔍 **Security Assessment Procedures**</summary>

Regular security testing and validation:

```bash
# Automated vulnerability scanning
#!/bin/bash
# security-scan.sh

# Network vulnerability scan
nmap -sV -sC --script vuln emuses.company.com

# Web application security scan
nikto -h https://emuses.company.com
sqlmap -u "https://emuses.company.com/api/models" --batch

# Vault security assessment
vault audit list
vault policy list
vault auth list

# SSL/TLS assessment
testssl.sh https://emuses.company.com

# Generate security report
cat > security-report.md << EOF
# Security Assessment Report

## Date: $(date)
## Scope: EMUSES Production Environment

### Findings Summary
- Network scan: $(nmap -sn emuses.company.com | grep -c "up")
- Web vulnerabilities: $(nikto -h https://emuses.company.com | grep -c "OSVDB")
- SSL rating: $(testssl.sh https://emuses.company.com | grep "Grade" | awk '{print $2}')

### Recommendations
1. Update identified vulnerable components
2. Implement additional WAF rules
3. Review and update security policies

### Next Assessment: $(date -d "+3 months")
EOF
```

**Schedule**: Quarterly automated scans, annual penetration testing

</details>

### Continuous Security Monitoring

<details markdown="1">
<summary>📊 **Security Metrics and KPIs**</summary>

Security performance monitoring and metrics:

```bash
# Security dashboard metrics
#!/bin/bash
# security-metrics.sh

# Failed authentication attempts
FAILED_AUTH=$(grep "authentication failed" /var/log/vault/audit.log | \
  grep "$(date +%Y-%m-%d)" | wc -l)

# Privilege escalation attempts
PRIV_ESC=$(grep "permission denied" /var/log/vault/audit.log | \
  grep "$(date +%Y-%m-%d)" | wc -l)

# Unusual access patterns
UNUSUAL_ACCESS=$(grep -E "(midnight|weekend)" /var/log/vault/audit.log | \
  grep "$(date +%Y-%m-%d)" | wc -l)

# Security event summary
cat > /dashboard/security-metrics.json << EOF
{
  "date": "$(date +%Y-%m-%d)",
  "failed_authentication": $FAILED_AUTH,
  "privilege_escalation_attempts": $PRIV_ESC,
  "unusual_access_patterns": $UNUSUAL_ACCESS,
  "vault_sealed": $(vault status | grep -q "Sealed.*false" && echo 0 || echo 1),
  "certificate_expiry_days": $(openssl x509 -enddate -noout -in /etc/ssl/certs/emuses.crt | \
    cut -d= -f2 | xargs -I{} date -d "{}" +%s | \
    awk -v now=$(date +%s) '{print int(($1-now)/86400)}')
}
EOF

# Alert thresholds
if [ "$FAILED_AUTH" -gt 50 ]; then
  echo "SECURITY ALERT: Excessive failed authentication attempts" | \
    mail -s "Security Alert" security@company.com
fi
```

**KPIs**: < 1% false positive rate, < 5 minutes detection time, 99.9% monitoring uptime

</details>

## **Incident Response and Forensics**

### Security Incident Response

<details markdown="1">
<summary>🚨 **Incident Response Procedures**</summary>

Comprehensive incident response framework:

```bash
#!/bin/bash
# incident-response.sh

INCIDENT_ID="INC-$(date +%Y%m%d-%H%M%S)"
INCIDENT_DIR="/forensics/$INCIDENT_ID"
mkdir -p "$INCIDENT_DIR"

# Evidence collection
echo "=== Incident Response: $INCIDENT_ID ===" | tee "$INCIDENT_DIR/incident.log"

# System state capture
vault status > "$INCIDENT_DIR/vault-status.txt"
systemctl status emuses > "$INCIDENT_DIR/service-status.txt"
ps aux > "$INCIDENT_DIR/processes.txt"
netstat -tulpn > "$INCIDENT_DIR/network.txt"

# Log collection
cp /var/log/vault/audit.log "$INCIDENT_DIR/"
cp /var/log/emuses/*.log "$INCIDENT_DIR/"
journalctl -u emuses --since "1 hour ago" > "$INCIDENT_DIR/system-logs.txt"

# Memory dump (if required)
if [ "$1" = "memory-dump" ]; then
  dd if=/dev/mem of="$INCIDENT_DIR/memory.dump" bs=1M
fi

# Network traffic capture
tcpdump -i any -w "$INCIDENT_DIR/network.pcap" &
TCPDUMP_PID=$!
sleep 300  # Capture 5 minutes
kill $TCPDUMP_PID

# Vault forensics
vault read sys/audit > "$INCIDENT_DIR/vault-audit-config.txt"
vault list auth/ldap/users > "$INCIDENT_DIR/vault-users.txt"

# Create forensics package
tar -czf "$INCIDENT_DIR.tar.gz" "$INCIDENT_DIR"
shasum -a 256 "$INCIDENT_DIR.tar.gz" > "$INCIDENT_DIR.tar.gz.sha256"

echo "Forensics package created: $INCIDENT_DIR.tar.gz"
echo "SHA256: $(cat $INCIDENT_DIR.tar.gz.sha256)"
```

**Response Times**: Detection < 5 minutes, containment < 30 minutes, recovery < 4 hours

</details>

### Digital Forensics

<details markdown="1">
<summary>🔬 **Forensic Analysis Tools**</summary>

Digital forensics and evidence analysis:

```bash
# Vault audit log analysis
#!/bin/bash
# vault-forensics.sh

AUDIT_LOG="/var/log/vault/audit.log"
ANALYSIS_DIR="/forensics/vault-analysis-$(date +%Y%m%d)"
mkdir -p "$ANALYSIS_DIR"

# Failed authentication analysis
jq -r 'select(.error != null and .type == "request") | 
  {time: .time, client_ip: .request.client_ip, error: .error}' \
  "$AUDIT_LOG" > "$ANALYSIS_DIR/failed-auth.json"

# Privilege escalation attempts
jq -r 'select(.request.operation == "update" and .request.path | contains("sys/auth")) |
  {time: .time, user: .auth.display_name, path: .request.path}' \
  "$AUDIT_LOG" > "$ANALYSIS_DIR/privilege-escalation.json"

# Data access patterns
jq -r 'select(.request.path | contains("secret/data")) |
  {time: .time, user: .auth.display_name, path: .request.path, operation: .request.operation}' \
  "$AUDIT_LOG" > "$ANALYSIS_DIR/data-access.json"

# Suspicious activity detection
python << EOF
import json
from collections import defaultdict
from datetime import datetime

# Load audit data
with open('$ANALYSIS_DIR/data-access.json', 'r') as f:
    events = [json.loads(line) for line in f if line.strip()]

# Analyze access patterns
user_activity = defaultdict(list)
for event in events:
    user_activity[event['user']].append(event)

# Detect unusual activity
for user, activities in user_activity.items():
    if len(activities) > 100:  # Threshold for unusual activity
        print(f"SUSPICIOUS: User {user} had {len(activities)} data access events")
    
    # Check for off-hours access
    off_hours = sum(1 for a in activities 
                   if datetime.fromisoformat(a['time'].replace('Z', '+00:00')).hour < 6 
                   or datetime.fromisoformat(a['time'].replace('Z', '+00:00')).hour > 22)
    
    if off_hours > 10:
        print(f"SUSPICIOUS: User {user} had {off_hours} off-hours access events")

EOF

# Generate forensics report
python << EOF
import json
from datetime import datetime

report = {
    'analysis_date': datetime.now().isoformat(),
    'incident_id': '$INCIDENT_ID',
    'summary': {
        'total_events': $(wc -l < "$AUDIT_LOG"),
        'failed_authentications': $(wc -l < "$ANALYSIS_DIR/failed-auth.json"),
        'privilege_escalation_attempts': $(wc -l < "$ANALYSIS_DIR/privilege-escalation.json"),
        'data_access_events': $(wc -l < "$ANALYSIS_DIR/data-access.json")
    },
    'recommendations': [
        'Review failed authentication sources',
        'Investigate privilege escalation attempts',
        'Validate data access patterns',
        'Update security policies as needed'
    ]
}

with open('$ANALYSIS_DIR/forensics-report.json', 'w') as f:
    json.dump(report, f, indent=2)
EOF
```

**Chain of Custody**: All evidence timestamped, hashed, and digitally signed

</details>

---

**🛡️ This comprehensive security and compliance guide ensures EMUSES deployments meet enterprise security requirements and regulatory compliance standards with HashiCorp Vault integration.**

---

*EMUSES Security and Compliance Guide - Enterprise Security Documentation*