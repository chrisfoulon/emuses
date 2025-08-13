#!/bin/bash

# EMUSES Database Migration Script
# Manages database migrations forward and backward

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATION_DIRECTION=""
TARGET_REVISION=""
ENVIRONMENT=${ENVIRONMENT:-production}
BACKUP_BEFORE_MIGRATION=${BACKUP_BEFORE_MIGRATION:-true}
DRY_RUN=${DRY_RUN:-false}

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] DIRECTION [TARGET]"
    echo ""
    echo "Directions:"
    echo "  forward, up       Apply pending migrations"
    echo "  backward, down    Rollback migrations to target"
    echo "  current           Show current migration status"
    echo "  validate          Validate database state"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment (production, staging, development)"
    echo "  -t, --target REVISION    Target migration revision"
    echo "  --dry-run               Show what would be done without executing"
    echo "  --no-backup             Skip backup before migration"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 forward                      # Apply all pending migrations"
    echo "  $0 backward --target abc123     # Rollback to specific revision"
    echo "  $0 current                      # Show current status"
    echo "  $0 validate                     # Validate database state"
}

# Function to validate database connection
validate_database_connection() {
    print_info "Validating database connection..."
    
    local db_host=${POSTGRES_HOST:-localhost}
    local db_port=${POSTGRES_PORT:-5432}
    local db_user=${POSTGRES_USER:-emuses_user}
    local db_name=${POSTGRES_DB:-emuses_db}
    
    if command -v pg_isready >/dev/null 2>&1; then
        if pg_isready -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name"; then
            print_success "Database connection validated"
        else
            print_error "Cannot connect to database"
            exit 1
        fi
    else
        print_warning "pg_isready not available, assuming database is accessible"
    fi
}

# Function to backup database before migration
backup_database() {
    print_info "Creating database backup before migration..."
    
    local backup_dir="/opt/emuses/backups/migration-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    local db_host=${POSTGRES_HOST:-localhost}
    local db_port=${POSTGRES_PORT:-5432}
    local db_user=${POSTGRES_USER:-emuses_user}
    local db_name=${POSTGRES_DB:-emuses_db}
    
    if command -v pg_dump >/dev/null 2>&1; then
        print_info "Dumping database schema and data..."
        
        if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
            -h "$db_host" -p "$db_port" -U "$db_user" \
            -f "$backup_dir/database_backup.sql" "$db_name"; then
            print_success "Database backup created: $backup_dir/database_backup.sql"
        else
            print_error "Database backup failed"
            exit 1
        fi
    else
        print_warning "pg_dump not available, skipping database backup"
    fi
    
    echo "MIGRATION_BACKUP_DIR=$backup_dir" > /tmp/emuses_migration_backup.env
}

# Function to get current migration status
get_migration_status() {
    print_info "Checking current migration status..."
    
    # Check if alembic is available
    if command -v alembic >/dev/null 2>&1; then
        print_info "Using Alembic for migration management"
        
        # Get current revision
        local current_revision
        current_revision=$(alembic current 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -n1)
        
        if [ -n "$current_revision" ]; then
            print_success "Current revision: $current_revision"
            echo "$current_revision"
        else
            print_warning "No migration history found"
            echo "none"
        fi
    else
        print_warning "Alembic not available, checking manual migration status"
        
        # Check for migration table in database
        if command -v psql >/dev/null 2>&1; then
            local db_host=${POSTGRES_HOST:-localhost}
            local db_port=${POSTGRES_PORT:-5432}
            local db_user=${POSTGRES_USER:-emuses_user}
            local db_name=${POSTGRES_DB:-emuses_db}
            
            PGPASSWORD="$POSTGRES_PASSWORD" psql \
                -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" \
                -c "SELECT version_num FROM alembic_version;" -t 2>/dev/null | xargs || echo "none"
        else
            print_warning "Cannot determine migration status"
            echo "unknown"
        fi
    fi
}

# Function to apply forward migrations
apply_forward_migrations() {
    print_info "Applying forward migrations..."
    
    if [ "$DRY_RUN" = "true" ]; then
        print_warning "DRY RUN: Would apply forward migrations"
        return 0
    fi
    
    if command -v alembic >/dev/null 2>&1; then
        if alembic upgrade head; then
            print_success "Forward migrations applied successfully"
        else
            print_error "Forward migration failed"
            exit 1
        fi
    else
        print_warning "Alembic not available, cannot apply migrations"
        exit 1
    fi
}

# Function to apply backward migrations
apply_backward_migrations() {
    local target="$1"
    
    print_info "Applying backward migrations to target: $target"
    
    if [ "$DRY_RUN" = "true" ]; then
        print_warning "DRY RUN: Would rollback to $target"
        return 0
    fi
    
    if command -v alembic >/dev/null 2>&1; then
        if alembic downgrade "$target"; then
            print_success "Backward migrations applied successfully"
        else
            print_error "Backward migration failed"
            exit 1
        fi
    else
        print_warning "Alembic not available, cannot apply migrations"
        exit 1
    fi
}

# Function to validate database state
validate_database_state() {
    print_info "Validating database state..."
    
    # Check if all required tables exist
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
        
        print_success "Database state validation passed"
    else
        print_warning "psql not available, cannot validate database state"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -t|--target)
            TARGET_REVISION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-backup)
            BACKUP_BEFORE_MIGRATION=false
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        forward|up|backward|down|current|validate)
            MIGRATION_DIRECTION="$1"
            shift
            ;;
        *)
            if [ -z "$TARGET_REVISION" ] && [ -n "$MIGRATION_DIRECTION" ]; then
                TARGET_REVISION="$1"
                shift
            else
                print_error "Unknown option: $1"
                show_usage
                exit 1
            fi
            ;;
    esac
done

# Main migration execution
print_header "🗄️  EMUSES Database Migration"
print_header "============================="

print_info "Environment: $ENVIRONMENT"
print_info "Direction: ${MIGRATION_DIRECTION:-not specified}"

if [ "$DRY_RUN" = "true" ]; then
    print_warning "DRY RUN MODE - No changes will be made"
fi

# Validate required parameters
if [ -z "$MIGRATION_DIRECTION" ]; then
    print_error "Migration direction is required"
    show_usage
    exit 1
fi

# Validate database connection
validate_database_connection

# Execute based on direction
case $MIGRATION_DIRECTION in
    forward|up)
        if [ "$BACKUP_BEFORE_MIGRATION" = "true" ]; then
            backup_database
        fi
        apply_forward_migrations
        validate_database_state
        ;;
    backward|down)
        if [ -z "$TARGET_REVISION" ]; then
            print_error "Target revision required for backward migration"
            exit 1
        fi
        if [ "$BACKUP_BEFORE_MIGRATION" = "true" ]; then
            backup_database
        fi
        apply_backward_migrations "$TARGET_REVISION"
        validate_database_state
        ;;
    current)
        current_revision=$(get_migration_status)
        print_info "Current migration revision: $current_revision"
        ;;
    validate)
        validate_database_state
        ;;
    *)
        print_error "Unknown migration direction: $MIGRATION_DIRECTION"
        show_usage
        exit 1
        ;;
esac

print_header "✅ MIGRATION COMPLETED SUCCESSFULLY"