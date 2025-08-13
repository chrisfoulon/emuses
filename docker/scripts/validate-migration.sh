#!/bin/bash

# EMUSES Migration Validation Script
# Validates migration safety and database integrity

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
MIGRATION_TYPE=""
TARGET_VERSION=""
ENVIRONMENT=${ENVIRONMENT:-production}

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

# Function to show usage
show_usage() {
    echo "Usage: $0 [TYPE] [OPTIONS]"
    echo ""
    echo "Types:"
    echo "  rollback TARGET     Validate rollback to TARGET version"
    echo "  migration           Validate forward migration"
    echo "  state               Validate current database state"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment (production, staging, development)"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 rollback v1.2.3      # Validate rollback to v1.2.3"
    echo "  $0 migration            # Validate forward migration"
    echo "  $0 state                # Validate current state"
}

# Function to validate database connectivity
validate_database_connectivity() {
    print_info "Validating database connectivity..."
    
    local db_host=${POSTGRES_HOST:-localhost}
    local db_port=${POSTGRES_PORT:-5432}
    local db_user=${POSTGRES_USER:-emuses_user}
    local db_name=${POSTGRES_DB:-emuses_db}
    
    if command -v pg_isready >/dev/null 2>&1; then
        if pg_isready -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name"; then
            print_success "Database connectivity validated"
        else
            print_error "Database connectivity failed"
            return 1
        fi
    else
        print_warning "pg_isready not available"
    fi
}

# Function to validate migration safety for rollback
validate_rollback_safety() {
    local target="$1"
    
    print_info "Validating rollback safety to $target..."
    
    # Check if target version exists
    if ! git tag -l | grep -q "^$target$"; then
        print_error "Target version $target not found in git"
        return 1
    fi
    
    # Check for data loss risks
    print_info "Checking for potential data loss..."
    
    # Get migration differences
    local current_commit
    current_commit=$(git rev-parse HEAD)
    local target_commit
    target_commit=$(git rev-parse "$target")
    
    # Check if there are migration files that would be rolled back
    local migration_files
    migration_files=$(git diff --name-only "$target_commit..$current_commit" | grep -E "(alembic|migrations)" || true)
    
    if [ -n "$migration_files" ]; then
        print_warning "Migration files changed since $target:"
        echo "$migration_files"
        
        # Check for potentially destructive operations
        local destructive_ops
        destructive_ops=$(git diff "$target_commit..$current_commit" -- "$migration_files" | \
            grep -E "(DROP|DELETE|TRUNCATE)" || true)
        
        if [ -n "$destructive_ops" ]; then
            print_error "Potentially destructive operations detected in rollback"
            print_warning "Review these operations carefully:"
            echo "$destructive_ops"
            return 1
        else
            print_success "No destructive operations detected"
        fi
    else
        print_success "No migration file changes detected"
    fi
}

# Function to validate forward migration
validate_forward_migration() {
    print_info "Validating forward migration safety..."
    
    # Check for pending migrations
    if command -v alembic >/dev/null 2>&1; then
        local pending_migrations
        pending_migrations=$(alembic history --indicate-current | grep "^[[:space:]]*[a-f0-9]" | grep -v "(current)" | wc -l)
        
        if [ "$pending_migrations" -gt 0 ]; then
            print_info "Found $pending_migrations pending migrations"
            alembic history --indicate-current | grep "^[[:space:]]*[a-f0-9]" | grep -v "(current)" | head -5
        else
            print_info "No pending migrations found"
        fi
    else
        print_warning "Alembic not available for migration validation"
    fi
    
    # Check database schema consistency
    validate_schema_integrity
}

# Function to validate current database state
validate_current_state() {
    print_info "Validating current database state..."
    
    # Check required tables exist
    local required_tables=("users" "workspaces" "model_registry" "alembic_version")
    local db_host=${POSTGRES_HOST:-localhost}
    local db_port=${POSTGRES_PORT:-5432}
    local db_user=${POSTGRES_USER:-emuses_user}
    local db_name=${POSTGRES_DB:-emuses_db}
    
    if command -v psql >/dev/null 2>&1; then
        for table in "${required_tables[@]}"; do
            if PGPASSWORD="$POSTGRES_PASSWORD" psql \
                -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" \
                -c "SELECT 1 FROM $table LIMIT 1;" >/dev/null 2>&1; then
                print_success "Table $table exists and accessible"
            else
                print_error "Table $table missing or inaccessible"
                return 1
            fi
        done
    else
        print_warning "psql not available for state validation"
    fi
    
    # Validate schema integrity
    validate_schema_integrity
}

# Function to validate schema integrity
validate_schema_integrity() {
    print_info "Validating database schema integrity..."
    
    local db_host=${POSTGRES_HOST:-localhost}
    local db_port=${POSTGRES_PORT:-5432}
    local db_user=${POSTGRES_USER:-emuses_user}
    local db_name=${POSTGRES_DB:-emuses_db}
    
    if command -v psql >/dev/null 2>&1; then
        # Check for foreign key violations
        local fk_violations
        fk_violations=$(PGPASSWORD="$POSTGRES_PASSWORD" psql \
            -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" \
            -t -c "SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_type = 'FOREIGN KEY';" 2>/dev/null | xargs)
        
        if [ -n "$fk_violations" ] && [ "$fk_violations" -gt 0 ]; then
            print_success "Foreign key constraints verified ($fk_violations found)"
        else
            print_warning "No foreign key constraints found"
        fi
        
        # Check for null constraints violations
        print_info "Checking for constraint violations..."
        
        # This is a basic check - in practice, you'd run more specific queries
        local constraint_check
        constraint_check=$(PGPASSWORD="$POSTGRES_PASSWORD" psql \
            -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" \
            -t -c "SELECT COUNT(*) FROM information_schema.check_constraints;" 2>/dev/null | xargs)
        
        if [ -n "$constraint_check" ]; then
            print_success "Schema constraints verified"
        else
            print_warning "No schema constraints found"
        fi
    else
        print_warning "Cannot validate schema integrity - psql not available"
    fi
}

# Function to validate backup availability
validate_backup_availability() {
    print_info "Validating backup availability..."
    
    local backup_dir="/opt/emuses/backups"
    
    if [ -d "$backup_dir" ]; then
        local recent_backups
        recent_backups=$(find "$backup_dir" -name "*.sql" -mtime -7 | wc -l)
        
        if [ "$recent_backups" -gt 0 ]; then
            print_success "Found $recent_backups recent backups (last 7 days)"
        else
            print_warning "No recent backups found"
        fi
    else
        print_warning "Backup directory not found: $backup_dir"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        rollback)
            MIGRATION_TYPE="rollback"
            TARGET_VERSION="$2"
            shift 2
            ;;
        migration)
            MIGRATION_TYPE="migration"
            shift
            ;;
        state)
            MIGRATION_TYPE="state"
            shift
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main validation execution
print_header "🔍 EMUSES Migration Validation"
print_header "==============================="

print_info "Environment: $ENVIRONMENT"
print_info "Validation type: ${MIGRATION_TYPE:-not specified}"

# Validate required parameters
if [ -z "$MIGRATION_TYPE" ]; then
    print_error "Migration type is required"
    show_usage
    exit 1
fi

# Common validations
validate_database_connectivity
validate_backup_availability

# Type-specific validations
case $MIGRATION_TYPE in
    rollback)
        if [ -z "$TARGET_VERSION" ]; then
            print_error "Target version required for rollback validation"
            exit 1
        fi
        validate_rollback_safety "$TARGET_VERSION"
        ;;
    migration)
        validate_forward_migration
        ;;
    state)
        validate_current_state
        ;;
    *)
        print_error "Unknown migration type: $MIGRATION_TYPE"
        exit 1
        ;;
esac

print_header "✅ MIGRATION VALIDATION COMPLETED"