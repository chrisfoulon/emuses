# EMUSES Admin Workflows for Research Environments

This document provides specific workflows and best practices for administering EMUSES in research environments, including universities, research labs, and academic institutions.

## Table of Contents

1. [Research Environment Overview](#research-environment-overview)
2. [User Lifecycle Management](#user-lifecycle-management)
3. [Resource Management for Research](#resource-management-for-research)
4. [Seasonal Operations](#seasonal-operations)
5. [Lab and Group Management](#lab-and-group-management)
6. [Grant and Project-Based Resource Allocation](#grant-and-project-based-resource-allocation)
7. [Educational Use Cases](#educational-use-cases)
8. [Research Data Management](#research-data-management)
9. [Compliance and Audit](#compliance-and-audit)

## Research Environment Overview

Research environments have unique characteristics that require specialized admin workflows:

- **Seasonal usage patterns** (academic semesters, summer research)
- **Hierarchical user structures** (faculty, postdocs, PhD students, undergrads)
- **Project-based resource allocation** (grants, research projects)
- **Educational vs research usage** (coursework vs original research)
- **Collaboration requirements** (shared datasets, joint projects)
- **Compliance needs** (IRB, data protection, funding requirements)

## User Lifecycle Management

### Academic Year Setup

#### Beginning of Semester

```bash
#!/bin/bash
# semester-setup.sh - Run at beginning of each semester

echo "=== Semester Setup - $(date) ==="

# 1. Bulk user creation for new students
# Read from CSV: email,name,organization,user_type
while IFS=, read -r email name org user_type; do
  if [[ "$user_type" == "undergraduate" ]]; then
    # Conservative quotas for undergraduates
    emuses admin add-user "$email" -p "TempPass$(date +%Y%m)" -o "$org"
    emuses admin set-quota "$email" storage_gb 5
    emuses admin set-quota "$email" concurrent_jobs 1
    emuses admin set-quota "$email" compute_hours 50
  elif [[ "$user_type" == "graduate" ]]; then
    # Higher quotas for graduate students
    emuses admin add-user "$email" -p "TempPass$(date +%Y%m)" -o "$org"
    emuses admin set-quota "$email" storage_gb 25
    emuses admin set-quota "$email" concurrent_jobs 2
    emuses admin set-quota "$email" compute_hours 200
  elif [[ "$user_type" == "faculty" ]]; then
    # Generous quotas for faculty
    emuses admin add-user "$email" -p "TempPass$(date +%Y%m)" -o "$org"
    emuses admin set-quota "$email" storage_gb 100
    emuses admin set-quota "$email" concurrent_jobs 5
    emuses admin set-quota "$email" compute_hours 1000
  fi
  echo "Created user: $email ($user_type)"
done < new-users-semester.csv

echo "Semester setup complete!"
```

#### End of Semester Cleanup

```bash
#!/bin/bash
# semester-cleanup.sh - Run at end of semester

echo "=== Semester Cleanup - $(date) ==="

# 1. Identify inactive student accounts
emuses admin list-users --limit 1000 > all-users.txt

# 2. Process departing students (from provided list)
while IFS= read -r email; do
  echo "Processing departure: $email"
  
  # Cancel any running jobs
  emuses admin system-status --detailed | grep "$email" | while read job_info; do
    job_id=$(echo "$job_info" | grep -o '[0-9a-f-]\{36\}')
    if [[ -n "$job_id" ]]; then
      emuses admin cancel-job "$job_id" --force
      echo "Cancelled job: $job_id for $email"
    fi
  done
  
  # Note: User deactivation would require additional endpoint
  # For now, document for manual review
  echo "$email - requires manual deactivation" >> departed-users.log
  
done < departing-students.txt

echo "Cleanup logged to departed-users.log"
```

### Research Staff Onboarding

#### New Postdoc/Research Staff

```bash
#!/bin/bash
# onboard-researcher.sh

# Usage: ./onboard-researcher.sh email@uni.edu "Dr. Jane Smith" "Neuroscience Lab" postdoc

EMAIL="$1"
NAME="$2"
LAB="$3"
POSITION="$4"

echo "=== Onboarding Researcher: $NAME ==="

# Create account with research-appropriate quotas
emuses admin add-user "$EMAIL" -p "Welcome$(date +%Y)" -o "$LAB"

case "$POSITION" in
  "postdoc")
    # Generous resources for postdocs
    emuses admin set-quota "$EMAIL" storage_gb 100
    emuses admin set-quota "$EMAIL" concurrent_jobs 4
    emuses admin set-quota "$EMAIL" compute_hours 800
    ;;
  "research_scientist")
    # High resources for research scientists
    emuses admin set-quota "$EMAIL" storage_gb 200
    emuses admin set-quota "$EMAIL" concurrent_jobs 5
    emuses admin set-quota "$EMAIL" compute_hours 1000
    ;;
  "phd_student")
    # Moderate resources for PhD students
    emuses admin set-quota "$EMAIL" storage_gb 50
    emuses admin set-quota "$EMAIL" concurrent_jobs 3
    emuses admin set-quota "$EMAIL" compute_hours 400
    ;;
esac

echo "Researcher onboarded successfully!"
echo "Email: $EMAIL"
echo "Temporary password: Welcome$(date +%Y)"
echo "Organization: $LAB"
echo "Please communicate credentials securely to user"
```

## Resource Management for Research

### Grant-Based Resource Allocation

#### Project-Specific Quota Management

```bash
#!/bin/bash
# project-quota-management.sh

# Allocate resources based on grant funding
PROJECT="$1"
TOTAL_STORAGE="$2"
TOTAL_COMPUTE="$3"

echo "=== Project Resource Allocation: $PROJECT ==="

# Read project members from file
# Format: email,role,allocation_percentage
while IFS=, read -r email role percentage; do
  storage_alloc=$(echo "$TOTAL_STORAGE * $percentage / 100" | bc)
  compute_alloc=$(echo "$TOTAL_COMPUTE * $percentage / 100" | bc)
  
  case "$role" in
    "PI")
      concurrent_jobs=5
      ;;
    "senior_researcher")
      concurrent_jobs=4
      ;;
    "researcher")
      concurrent_jobs=3
      ;;
    "student")
      concurrent_jobs=2
      ;;
  esac
  
  echo "Allocating to $email ($role): ${storage_alloc}GB storage, ${compute_alloc}h compute"
  
  emuses admin set-quota "$email" storage_gb "$storage_alloc"
  emuses admin set-quota "$email" compute_hours "$compute_alloc"
  emuses admin set-quota "$email" concurrent_jobs "$concurrent_jobs"
  
done < "project-${PROJECT}-members.csv"

echo "Project resource allocation complete!"
```

### Dynamic Resource Scaling

#### Conference/Deadline Preparation

```bash
#!/bin/bash
# conference-prep-scaling.sh - Temporary resource boost for deadlines

echo "=== Conference Deadline Resource Boost ==="

# List of users needing temporary increase
USERS=("phd1@uni.edu" "phd2@uni.edu" "postdoc@uni.edu")

# Save current quotas for later restoration
for user in "${USERS[@]}"; do
  # This would require a quota query endpoint to save current values
  echo "# Saving quotas for $user for later restoration" >> quota-backup.sh
done

# Apply temporary boost
for user in "${USERS[@]}"; do
  echo "Boosting resources for $user"
  emuses admin set-quota "$user" storage_gb 200
  emuses admin set-quota "$user" concurrent_jobs 6
  emuses admin set-quota "$user" compute_hours 2000
done

echo "Temporary boost applied. Remember to restore quotas after deadline!"
echo "Restoration commands saved in quota-backup.sh"
```

## Seasonal Operations

### Summer Research Intensive

```bash
#!/bin/bash
# summer-research-setup.sh

echo "=== Summer Research Period Setup ==="

# Higher resource allocation for intensive summer research
SUMMER_RESEARCHERS=("summer-student1@uni.edu" "summer-student2@uni.edu" "visiting-scholar@uni.edu")

for user in "${SUMMER_RESEARCHERS[@]}"; do
  echo "Setting up summer research allocation for $user"
  
  # Summer students get enhanced resources
  emuses admin set-quota "$user" storage_gb 75
  emuses admin set-quota "$user" concurrent_jobs 3
  emuses admin set-quota "$user" compute_hours 600
done

# Monitor system load during high-usage period
echo "#!/bin/bash" > summer-monitoring.sh
echo "# Run this daily during summer research period" >> summer-monitoring.sh
echo "emuses admin system-status --detailed > daily-status-\$(date +%Y%m%d).log" >> summer-monitoring.sh
echo "# Alert if running jobs > 80% capacity" >> summer-monitoring.sh
chmod +x summer-monitoring.sh

echo "Summer setup complete. Use ./summer-monitoring.sh for daily monitoring"
```

### Winter Break Maintenance

```bash
#!/bin/bash
# winter-maintenance.sh

echo "=== Winter Break Maintenance Period ==="

# 1. System health check
emuses admin system-status --detailed > pre-maintenance-status.log

# 2. Cancel non-essential jobs
echo "Checking for long-running jobs to cancel..."
emuses admin system-status --detailed | grep -A 50 "Job Queues"

# 3. User activity audit
echo "=== User Activity Audit ===" > winter-audit.log
emuses admin list-users --limit 1000 >> winter-audit.log

# 4. Prepare for next semester
echo "Creating next semester preparation checklist:"
cat << EOF > next-semester-prep.txt
Next Semester Preparation Checklist:
[ ] Update user lists from registrar
[ ] Prepare new course quotas
[ ] Review and update default quotas
[ ] Test system after maintenance
[ ] Communicate any changes to users
[ ] Update documentation
EOF

echo "Maintenance preparation complete!"
```

## Lab and Group Management

### Multi-Lab Environment

```bash
#!/bin/bash
# lab-management.sh

# Manage resources across multiple research labs
declare -A LAB_QUOTAS
LAB_QUOTAS["Computational Biology Lab"]="storage:500,compute:5000"
LAB_QUOTAS["Machine Learning Lab"]="storage:1000,compute:8000"
LAB_QUOTAS["Neuroscience Lab"]="storage:300,compute:3000"

for lab in "${!LAB_QUOTAS[@]}"; do
  echo "=== Managing $lab ==="
  
  # Get lab-specific quota limits
  IFS=',' read -ra LIMITS <<< "${LAB_QUOTAS[$lab]}"
  
  for limit in "${LIMITS[@]}"; do
    IFS=':' read -ra PARTS <<< "$limit"
    quota_type="${PARTS[0]}"
    total_quota="${PARTS[1]}"
    
    echo "Lab $lab total $quota_type quota: $total_quota"
  done
  
  # Get lab members
  emuses admin list-users --limit 1000 | grep "$lab" > "${lab// /_}_members.txt"
  
  echo "Lab member list saved to ${lab// /_}_members.txt"
done
```

### Shared Resource Coordination

```bash
#!/bin/bash
# shared-resource-coordination.sh

echo "=== Shared Resource Coordination ==="

# Monitor high-demand periods
current_hour=$(date +%H)
day_of_week=$(date +%u)  # 1=Monday, 7=Sunday

# Adjust concurrent job limits based on demand patterns
if [[ $day_of_week -le 5 ]] && [[ $current_hour -ge 9 ]] && [[ $current_hour -le 17 ]]; then
  echo "Peak hours detected - implementing fair-share policies"
  
  # During peak hours, reduce concurrent jobs for large jobs
  # This would require more sophisticated quota management
  
  # Get current system load
  emuses admin system-status --detailed > current-load.log
  
  running_jobs=$(grep "Running:" current-load.log | grep -o '[0-9]\+')
  
  if [[ $running_jobs -gt 20 ]]; then
    echo "High load detected ($running_jobs running jobs)"
    echo "Consider implementing temporary limits"
  fi
fi
```

## Educational Use Cases

### Course-Specific Setup

```bash
#!/bin/bash
# course-setup.sh

COURSE="$1"  # e.g., "CS280-MachineLearning"
INSTRUCTOR="$2"
SEMESTER="$3"

echo "=== Setting up course: $COURSE ==="

# Create course-specific organization
COURSE_ORG="$COURSE-$SEMESTER"

# Set up instructor with course admin privileges
echo "Setting up instructor: $INSTRUCTOR"
emuses admin set-quota "$INSTRUCTOR" storage_gb 200
emuses admin set-quota "$INSTRUCTOR" concurrent_jobs 8
emuses admin set-quota "$INSTRUCTOR" compute_hours 2000

# Course-specific quotas for assignments
ASSIGNMENT_STORAGE=10  # GB per student
ASSIGNMENT_COMPUTE=100  # Hours per semester
CONCURRENT_JOBS=2      # For coursework

# Read student list
while IFS= read -r student_email; do
  echo "Enrolling student: $student_email"
  
  emuses admin add-user "$student_email" -p "Course$(date +%Y%m)" -o "$COURSE_ORG"
  emuses admin set-quota "$student_email" storage_gb "$ASSIGNMENT_STORAGE"
  emuses admin set-quota "$student_email" concurrent_jobs "$CONCURRENT_JOBS"
  emuses admin set-quota "$student_email" compute_hours "$ASSIGNMENT_COMPUTE"
  
done < "${COURSE}-roster.txt"

echo "Course setup complete for $COURSE"
echo "Total students enrolled: $(wc -l < ${COURSE}-roster.txt)"
```

### Assignment Deadlines

```bash
#!/bin/bash
# assignment-deadline-management.sh

ASSIGNMENT="$1"
DEADLINE="$2"
COURSE="$3"

echo "=== Managing Assignment Deadline: $ASSIGNMENT ==="

# Get course students
emuses admin list-users --limit 1000 | grep "$COURSE" > course-students.txt

# Increase temporary limits before deadline
days_until_deadline=$(( ($(date -d "$DEADLINE" +%s) - $(date +%s)) / 86400 ))

if [[ $days_until_deadline -le 3 ]]; then
  echo "Deadline approaching in $days_until_deadline days - boosting resources"
  
  while IFS= read -r line; do
    if [[ $line == *"$COURSE"* ]]; then
      email=$(echo "$line" | grep -o '[^[:space:]]*@[^[:space:]]*')
      if [[ -n "$email" ]]; then
        # Temporary boost for deadline crunch
        emuses admin set-quota "$email" concurrent_jobs 3
        emuses admin set-quota "$email" compute_hours 150
        echo "Boosted resources for $email"
      fi
    fi
  done < course-students.txt
fi

# Monitor system load during deadline period
emuses admin system-status --detailed > "assignment-${ASSIGNMENT}-load.log"
```

## Research Data Management

### Data-Intensive Project Setup

```bash
#!/bin/bash
# data-intensive-setup.sh

PROJECT="$1"
DATASET_SIZE="$2"  # in GB
TEAM_SIZE="$3"

echo "=== Setting up data-intensive project: $PROJECT ==="

# Calculate storage requirements
TOTAL_STORAGE=$(echo "$DATASET_SIZE * 3" | bc)  # 3x for processing space
PER_USER_STORAGE=$(echo "$TOTAL_STORAGE / $TEAM_SIZE" | bc)

echo "Dataset size: ${DATASET_SIZE}GB"
echo "Total storage allocated: ${TOTAL_STORAGE}GB"
echo "Per-user storage: ${PER_USER_STORAGE}GB"

# Read team members
while IFS=, read -r email role; do
  case "$role" in
    "data_scientist"|"senior_researcher")
      user_storage=$(echo "$PER_USER_STORAGE * 1.5" | bc)
      concurrent_jobs=4
      ;;
    "analyst"|"researcher")
      user_storage="$PER_USER_STORAGE"
      concurrent_jobs=3
      ;;
    "student"|"intern")
      user_storage=$(echo "$PER_USER_STORAGE * 0.7" | bc)
      concurrent_jobs=2
      ;;
  esac
  
  echo "Allocating ${user_storage}GB storage to $email ($role)"
  emuses admin set-quota "$email" storage_gb "$user_storage"
  emuses admin set-quota "$email" concurrent_jobs "$concurrent_jobs"
  emuses admin set-quota "$email" compute_hours 500
  
done < "${PROJECT}-team.csv"

echo "Data-intensive project setup complete!"
```

### Collaborative Research Setup

```bash
#!/bin/bash
# collaborative-research-setup.sh

COLLABORATION="$1"
LEAD_INSTITUTION="$2"

echo "=== Setting up collaborative research: $COLLABORATION ==="

# Set up shared resource pool for collaboration
# Higher quotas for collaboration coordinators
while IFS=, read -r email institution role; do
  org="$COLLABORATION-$institution"
  
  if [[ "$role" == "coordinator" ]]; then
    emuses admin add-user "$email" -p "Collab$(date +%Y)" -o "$org"
    emuses admin set-quota "$email" storage_gb 200
    emuses admin set-quota "$email" concurrent_jobs 6
    emuses admin set-quota "$email" compute_hours 1500
  elif [[ "$role" == "researcher" ]]; then
    emuses admin add-user "$email" -p "Collab$(date +%Y)" -o "$org"
    emuses admin set-quota "$email" storage_gb 100
    emuses admin set-quota "$email" concurrent_jobs 4
    emuses admin set-quota "$email" compute_hours 800
  fi
  
  echo "Setup $email from $institution as $role"
done < "${COLLABORATION}-participants.csv"

echo "Collaborative research setup complete!"
```

## Compliance and Audit

### Usage Reporting

```bash
#!/bin/bash
# usage-reporting.sh

REPORT_PERIOD="$1"  # e.g., "2024-01" for January 2024
OUTPUT_DIR="reports"

echo "=== Generating Usage Report for $REPORT_PERIOD ==="

mkdir -p "$OUTPUT_DIR"

# System status report
emuses admin system-status --detailed > "$OUTPUT_DIR/system-status-$REPORT_PERIOD.log"

# User activity report
emuses admin list-users --limit 1000 > "$OUTPUT_DIR/user-list-$REPORT_PERIOD.txt"

# Count users by organization
echo "=== Users by Organization ===" > "$OUTPUT_DIR/org-summary-$REPORT_PERIOD.txt"
grep -o '"organization":"[^"]*"' "$OUTPUT_DIR/user-list-$REPORT_PERIOD.txt" | \
  sort | uniq -c | sort -nr >> "$OUTPUT_DIR/org-summary-$REPORT_PERIOD.txt"

# Active vs inactive users
active_users=$(grep -c '"is_active":true' "$OUTPUT_DIR/user-list-$REPORT_PERIOD.txt")
total_users=$(wc -l < "$OUTPUT_DIR/user-list-$REPORT_PERIOD.txt")

echo "=== Usage Summary for $REPORT_PERIOD ===" > "$OUTPUT_DIR/summary-$REPORT_PERIOD.txt"
echo "Total users: $total_users" >> "$OUTPUT_DIR/summary-$REPORT_PERIOD.txt"
echo "Active users: $active_users" >> "$OUTPUT_DIR/summary-$REPORT_PERIOD.txt"
echo "Inactive users: $((total_users - active_users))" >> "$OUTPUT_DIR/summary-$REPORT_PERIOD.txt"

echo "Reports generated in $OUTPUT_DIR/"
```

### Audit Trail

```bash
#!/bin/bash
# audit-trail.sh

AUDIT_DATE="$(date +%Y%m%d)"
AUDIT_DIR="audit-$AUDIT_DATE"

echo "=== Creating Audit Trail for $AUDIT_DATE ==="

mkdir -p "$AUDIT_DIR"

# Capture current system state
emuses admin system-status --detailed > "$AUDIT_DIR/system-state.log"
emuses admin list-users --limit 10000 > "$AUDIT_DIR/all-users.json"

# Create audit summary
cat << EOF > "$AUDIT_DIR/audit-summary.txt"
EMUSES System Audit - $AUDIT_DATE
Generated: $(date)

System Status: $(grep -o '"status":"[^"]*"' "$AUDIT_DIR/system-state.log" | head -1)

User Statistics:
- Total users: $(wc -l < "$AUDIT_DIR/all-users.json")
- Active users: $(grep -c '"is_active":true' "$AUDIT_DIR/all-users.json")
- Verified users: $(grep -c '"is_verified":true' "$AUDIT_DIR/all-users.json")
- Superusers: $(grep -c '"is_superuser":true' "$AUDIT_DIR/all-users.json")

Organizations represented: $(grep -o '"organization":"[^"]*"' "$AUDIT_DIR/all-users.json" | sort -u | wc -l)

System Health Checks:
$(grep -A 20 '"checks":' "$AUDIT_DIR/system-state.log" || echo "Health check data not available")

Job Queue Status:
$(grep -A 10 "Job Queues" "$AUDIT_DIR/system-state.log" || echo "Job queue data not available")

Audit completed: $(date)
EOF

echo "Audit trail created in $AUDIT_DIR/"
echo "Key files:"
echo "  - audit-summary.txt (executive summary)"
echo "  - system-state.log (detailed system status)"
echo "  - all-users.json (complete user list)"
```

## Best Practices for Research Environments

### 1. User Communication

```bash
# Create user notification templates
cat << 'EOF' > templates/new-user-welcome.txt
Welcome to EMUSES!

Your account has been created with the following details:
- Email: ${EMAIL}
- Organization: ${ORGANIZATION}
- Temporary Password: ${TEMP_PASSWORD}

Your resource quotas:
- Storage: ${STORAGE_GB}GB
- Concurrent Jobs: ${CONCURRENT_JOBS}
- Compute Hours: ${COMPUTE_HOURS}/month

Please log in and change your password immediately.

For help and documentation, visit: [your documentation URL]

Best regards,
EMUSES Admin Team
EOF
```

### 2. Automated Monitoring

```bash
#!/bin/bash
# research-monitoring.sh - Run via cron

# Daily monitoring specific to research environments
ALERT_EMAIL="admin@institution.edu"

# Check for unusual patterns
emuses admin system-status --detailed > daily-status.log

# Alert on high load
running_jobs=$(grep "Running:" daily-status.log | grep -o '[0-9]\+')
if [[ $running_jobs -gt 50 ]]; then
  echo "High job load detected: $running_jobs jobs running" | \
    mail -s "EMUSES High Load Alert" "$ALERT_EMAIL"
fi

# Check for quota exhaustion
# This would require additional quota usage endpoints

# Weekly user activity summary
if [[ $(date +%u) -eq 1 ]]; then  # Monday
  emuses admin list-users --limit 1000 | \
    mail -s "EMUSES Weekly User Summary" "$ALERT_EMAIL"
fi
```

### 3. Resource Planning

```bash
#!/bin/bash
# resource-planning.sh

echo "=== Resource Planning Analysis ==="

# Current utilization
emuses admin system-status --detailed > current-usage.log

# Project growth estimation
current_users=$(emuses admin list-users --limit 1000 | wc -l)
echo "Current users: $current_users"

# Estimate resources needed for next semester
# Based on historical patterns
next_semester_users=$(echo "$current_users * 1.2" | bc | cut -d. -f1)
echo "Estimated next semester users: $next_semester_users"

# Resource recommendations
echo "=== Resource Recommendations ==="
echo "- Plan for $next_semester_users users"
echo "- Consider storage expansion if current usage > 80%"
echo "- Monitor peak usage during assignment deadlines"
echo "- Review quota policies based on actual usage patterns"
```

---

*This document provides research-specific workflows for EMUSES administration. Adapt these examples to your institution's specific needs and policies.*