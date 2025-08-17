#!/bin/bash

# EMUSES Deployment Rollback Script
# Safely rollback to a previous deployment version

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
ENVIRONMENT=${ENVIRONMENT:-production}
TARGET_VERSION=""
FORCE_ROLLBACK=${FORCE_ROLLBACK:-false}
BACKUP_BEFORE_ROLLBACK=${BACKUP_BEFORE_ROLLBACK:-true}
ROLLBACK_TIMEOUT=${ROLLBACK_TIMEOUT:-600}  # 10 minutes

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --version VERSION    Target version to rollback to (required)"
    echo "  -e, --environment ENV    Environment (production, staging, development)"
    echo "  -f, --force             Force rollback without confirmation"
    echo "  --no-backup             Skip backup before rollback"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --version v1.2.3 --environment production"
    echo "  $0 -v v1.2.3 -e staging --force"
}

# Function to confirm action
confirm_action() {
    local prompt="$1"
    
    if [ "$FORCE_ROLLBACK" = "true" ]; then
        print_warning "Force mode enabled - skipping confirmation"
        return 0
    fi
    
    echo -e "${YELLOW}$prompt${NC}"
    read -p "Continue? (yes/no): " response
    
    case $response in
        [Yy][Ee][Ss]|[Yy])
            return 0
            ;;
        *)
            print_error "Rollback cancelled by user"
            exit 1
            ;;
    esac
}

# Function to validate target version exists
validate_target_version() {
    local version="$1"
    
    print_info "Validating target version: $version"
    
    # Check if version tag exists in git
    if git tag -l | grep -q "^$version$"; then
        print_success "Version $version exists in git"
    else
        print_error "Version $version not found in git tags"
        print_info "Available versions:"
        git tag -l | tail -10
        exit 1
    fi
    
    # Check if docker images exist for this version
    local image_name="emuses:$version"
    if docker images -q "$image_name" | grep -q .; then
        print_success "Docker image $image_name available"
    else
        print_warning "Docker image $image_name not found locally"
        print_info "Will attempt to pull from registry during rollback"
    fi
}

# Function to get current version
get_current_version() {
    # Try to get version from git
    local current_version
    current_version=$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)
    echo "$current_version"
}

# Function to backup current deployment
backup_current_deployment() {
    print_info "Creating backup of current deployment..."
    
    local backup_dir="/opt/emuses/backups/rollback-$(date +%Y%m%d_%H%M%S)"
    local current_version
    current_version=$(get_current_version)
    
    # Create backup using existing backup scripts
    if [ -f "$SCRIPT_DIR/backup-postgres.sh" ]; then
        print_info "Backing up database..."
        if timeout $ROLLBACK_TIMEOUT "$SCRIPT_DIR/backup-postgres.sh"; then
            print_success "Database backup completed"
        else
            print_error "Database backup failed"
            exit 1
        fi
    fi
    
    # Backup current configuration
    print_info "Backing up current configuration..."
    mkdir -p "$backup_dir"
    
    # Backup docker-compose files
    cp docker-compose*.yml "$backup_dir/" 2>/dev/null || true
    
    # Backup environment files if they exist
    cp .env.* "$backup_dir/" 2>/dev/null || true
    
    # Save current version info
    echo "PREVIOUS_VERSION=$current_version" > "$backup_dir/rollback_info.env"
    echo "ROLLBACK_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$backup_dir/rollback_info.env"
    echo "ROLLBACK_USER=${USER:-unknown}" >> "$backup_dir/rollback_info.env"
    echo "ENVIRONMENT=$ENVIRONMENT" >> "$backup_dir/rollback_info.env"
    
    print_success "Backup saved to: $backup_dir"
    echo "BACKUP_DIR=$backup_dir" > /tmp/emuses_rollback_backup.env
}

# Function to stop current services
stop_services() {
    print_info "Stopping current services..."
    
    local compose_file=""
    case $ENVIRONMENT in
        production) compose_file="docker-compose.production.yml" ;;
        staging) compose_file="docker-compose.staging.yml" ;;
        *) compose_file="docker-compose.yml" ;;
    esac
    
    if [ -f "$compose_file" ]; then
        if timeout $ROLLBACK_TIMEOUT docker-compose -f "$compose_file" down; then
            print_success "Services stopped successfully"
        else
            print_error "Failed to stop services"
            exit 1
        fi
    else
        print_warning "Compose file $compose_file not found, skipping service stop"
    fi
}

# Function to checkout target version
checkout_target_version() {
    local version="$1"
    
    print_info "Checking out version: $version"
    
    # Stash any local changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        print_warning "Stashing local changes..."
        git stash push -m "Rollback stash - $(date)"
    fi
    
    # Checkout target version
    if git checkout "$version"; then
        print_success "Checked out version $version"
    else
        print_error "Failed to checkout version $version"
        exit 1
    fi
}

# Function to start services with target version
start_services() {
    print_info "Starting services with target version..."
    
    local compose_file=""
    case $ENVIRONMENT in
        production) compose_file="docker-compose.production.yml" ;;
        staging) compose_file="docker-compose.staging.yml" ;;
        *) compose_file="docker-compose.yml" ;;
    esac
    
    if [ -f "$compose_file" ]; then
        # Pull/build images for target version
        print_info "Pulling/building images for target version..."
        if timeout $ROLLBACK_TIMEOUT docker-compose -f "$compose_file" pull || \
           timeout $ROLLBACK_TIMEOUT docker-compose -f "$compose_file" build; then
            print_success "Images ready"
        else
            print_error "Failed to prepare images"
            exit 1
        fi
        
        # Start services
        if timeout $ROLLBACK_TIMEOUT docker-compose -f "$compose_file" up -d; then
            print_success "Services started successfully"
        else
            print_error "Failed to start services"
            exit 1
        fi
    else
        print_error "Compose file $compose_file not found"
        exit 1
    fi
}

# Function to validate rollback
validate_rollback() {
    print_info "Validating rollback deployment..."
    
    # Run health checks
    if [ -f "$SCRIPT_DIR/health-check.sh" ]; then
        sleep 10  # Give services time to start
        
        if timeout $ROLLBACK_TIMEOUT "$SCRIPT_DIR/health-check.sh"; then
            print_success "Rollback validation passed"
        else
            print_error "Rollback validation failed"
            return 1
        fi
    else
        print_warning "Health check script not found, skipping validation"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            TARGET_VERSION="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_ROLLBACK=true
            shift
            ;;
        --no-backup)
            BACKUP_BEFORE_ROLLBACK=false
            shift
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

# Main rollback execution
print_header "🔄 EMUSES Deployment Rollback"
print_header "=============================="

# Validate required parameters
if [ -z "$TARGET_VERSION" ]; then
    print_error "Target version is required"
    show_usage
    exit 1
fi

current_version=$(get_current_version)
print_info "Current version: $current_version"
print_info "Target version: $TARGET_VERSION"
print_info "Environment: $ENVIRONMENT"

# Validate target version
validate_target_version "$TARGET_VERSION"

# Confirm rollback
confirm_action "⚠️  This will rollback the $ENVIRONMENT deployment from $current_version to $TARGET_VERSION"

# Execute rollback steps
if [ "$BACKUP_BEFORE_ROLLBACK" = "true" ]; then
    backup_current_deployment
fi

stop_services
checkout_target_version "$TARGET_VERSION"
start_services

# Validate rollback
if validate_rollback; then
    print_header "🎉 ROLLBACK COMPLETED SUCCESSFULLY"
    print_success "Deployment rolled back to version $TARGET_VERSION"
    print_info "Environment: $ENVIRONMENT"
    print_info "Previous version: $current_version"
    
    if [ "$BACKUP_BEFORE_ROLLBACK" = "true" ] && [ -f "/tmp/emuses_rollback_backup.env" ]; then
        source /tmp/emuses_rollback_backup.env
        print_info "Backup location: $BACKUP_DIR"
    fi
    
    exit 0
else
    print_header "💥 ROLLBACK VALIDATION FAILED"
    print_error "Rollback completed but validation failed"
    print_warning "Manual intervention may be required"
    exit 1
fi