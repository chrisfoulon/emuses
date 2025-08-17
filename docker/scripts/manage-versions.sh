#!/bin/bash

# EMUSES Version Management Script
# Manages deployment versions, tags, and cleanup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
ACTION=""
VERSION_TAG=""
CLEANUP_KEEP=${CLEANUP_KEEP:-10}  # Keep last 10 versions by default

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_header() { echo -e "${CYAN}$1${NC}"; }

# Function to show usage
show_usage() {
    echo "Usage: $0 [ACTION] [OPTIONS]"
    echo ""
    echo "Actions:"
    echo "  list                List available versions"
    echo "  current             Show current version"
    echo "  tag VERSION         Create a new version tag"
    echo "  cleanup             Clean up old versions"
    echo "  info VERSION        Show detailed version information"
    echo ""
    echo "Options:"
    echo "  --keep NUM          Number of versions to keep during cleanup (default: 10)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 list                        # List all versions"
    echo "  $0 current                     # Show current version"
    echo "  $0 tag v1.2.3                  # Create version tag v1.2.3"
    echo "  $0 cleanup --keep 5            # Keep only last 5 versions"
    echo "  $0 info v1.2.3                 # Show info for version v1.2.3"
}

# Function to list available versions
list_versions() {
    print_info "Available versions:"
    
    # List git tags
    if git tag -l | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' >/dev/null; then
        echo "Git Tags:"
        git tag -l | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -20
    else
        print_warning "No semantic version tags found"
    fi
    
    echo ""
    
    # List docker images
    print_info "Available Docker images:"
    if docker images emuses --format "table {{.Tag}}\t{{.CreatedSince}}\t{{.Size}}" | grep -v latest | head -20; then
        print_success "Docker images listed"
    else
        print_warning "No Docker images found for emuses"
    fi
}

# Function to get current version
get_current_version() {
    print_info "Determining current version..."
    
    # Try to get exact tag first
    local current_tag
    current_tag=$(git describe --exact-match --tags 2>/dev/null || echo "")
    
    if [ -n "$current_tag" ]; then
        print_success "Current version: $current_tag (exact tag)"
        echo "$current_tag"
    else
        # Get closest tag with commit info
        local describe_version
        describe_version=$(git describe --tags 2>/dev/null || echo "")
        
        if [ -n "$describe_version" ]; then
            print_success "Current version: $describe_version (with commits)"
            echo "$describe_version"
        else
            # Fallback to commit hash
            local commit_hash
            commit_hash=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
            print_warning "Current version: $commit_hash (commit hash)"
            echo "$commit_hash"
        fi
    fi
}

# Function to create version tag
create_version_tag() {
    local version="$1"
    
    print_info "Creating version tag: $version"
    
    # Validate version format (semantic versioning)
    if ! echo "$version" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$'; then
        print_error "Invalid version format. Expected: v1.2.3 or v1.2.3-alpha"
        exit 1
    fi
    
    # Check if tag already exists
    if git tag -l | grep -q "^$version$"; then
        print_error "Tag $version already exists"
        exit 1
    fi
    
    # Check if working directory is clean
    if ! git diff --quiet || ! git diff --cached --quiet; then
        print_error "Working directory is not clean. Commit or stash changes first."
        exit 1
    fi
    
    # Create annotated tag
    local tag_message="Release $version - $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if git tag -a "$version" -m "$tag_message"; then
        print_success "Version tag $version created successfully"
        
        # Show tag info
        git show --no-patch --format="Tag: %D%nDate: %ai%nAuthor: %an <%ae>%nMessage: %s" "$version"
        
        print_info "To push the tag: git push origin $version"
    else
        print_error "Failed to create version tag"
        exit 1
    fi
}

# Function to cleanup old versions
cleanup_versions() {
    local keep_count="$1"
    
    print_info "Cleaning up old versions (keeping last $keep_count)"
    
    # Cleanup old git tags
    print_info "Checking git tags for cleanup..."
    local all_tags
    all_tags=$(git tag -l | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V)
    local tag_count
    tag_count=$(echo "$all_tags" | wc -l)
    
    if [ "$tag_count" -gt "$keep_count" ]; then
        local tags_to_delete
        tags_to_delete=$(echo "$all_tags" | head -n $((tag_count - keep_count)))
        
        print_warning "Found $((tag_count - keep_count)) old tags to cleanup:"
        echo "$tags_to_delete"
        
        echo "Delete these tags? (yes/no):"
        read -r response
        case $response in
            [Yy][Ee][Ss]|[Yy])
                echo "$tags_to_delete" | while read -r tag; do
                    if git tag -d "$tag"; then
                        print_success "Deleted tag: $tag"
                    else
                        print_error "Failed to delete tag: $tag"
                    fi
                done
                ;;
            *)
                print_info "Skipping tag cleanup"
                ;;
        esac
    else
        print_info "No old tags to cleanup ($tag_count <= $keep_count)"
    fi
    
    # Cleanup old docker images
    print_info "Checking Docker images for cleanup..."
    local old_images
    old_images=$(docker images emuses --format "{{.Tag}}" | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | head -n -"$keep_count" || true)
    
    if [ -n "$old_images" ]; then
        print_warning "Found old Docker images to cleanup:"
        echo "$old_images"
        
        echo "Delete these images? (yes/no):"
        read -r response
        case $response in
            [Yy][Ee][Ss]|[Yy])
                echo "$old_images" | while read -r tag; do
                    if docker rmi "emuses:$tag" 2>/dev/null; then
                        print_success "Deleted image: emuses:$tag"
                    else
                        print_warning "Failed to delete image: emuses:$tag"
                    fi
                done
                ;;
            *)
                print_info "Skipping image cleanup"
                ;;
        esac
    else
        print_info "No old Docker images to cleanup"
    fi
    
    # Cleanup docker build cache
    print_info "Cleaning up Docker build cache..."
    if docker builder prune -f >/dev/null 2>&1; then
        print_success "Docker build cache cleaned"
    else
        print_warning "Failed to clean Docker build cache"
    fi
}

# Function to show version info
show_version_info() {
    local version="$1"
    
    print_info "Version information for: $version"
    
    # Check if it's a git tag
    if git tag -l | grep -q "^$version$"; then
        print_success "Git tag found"
        echo ""
        echo "Git Tag Information:"
        git show --no-patch --format="Tag: %D%nDate: %ai%nAuthor: %an <%ae>%nCommit: %H%nMessage: %s" "$version"
        echo ""
        
        # Show files changed since previous version
        local prev_version
        prev_version=$(git tag -l | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | grep -B1 "^$version$" | head -1)
        
        if [ -n "$prev_version" ] && [ "$prev_version" != "$version" ]; then
            echo "Changes since $prev_version:"
            git diff --name-only "$prev_version..$version" | head -20
        fi
    else
        print_warning "Git tag not found"
    fi
    
    # Check if docker image exists
    if docker images emuses:"$version" --format "{{.Tag}}" | grep -q "^$version$"; then
        print_success "Docker image found"
        echo ""
        echo "Docker Image Information:"
        docker images emuses:"$version" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}"
    else
        print_warning "Docker image not found"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        list|current|cleanup)
            ACTION="$1"
            shift
            ;;
        tag)
            ACTION="$1"
            VERSION_TAG="$2"
            shift 2
            ;;
        info)
            ACTION="$1"
            VERSION_TAG="$2"
            shift 2
            ;;
        --keep)
            CLEANUP_KEEP="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            if [ -z "$VERSION_TAG" ] && [ "$ACTION" = "tag" ]; then
                VERSION_TAG="$1"
                shift
            else
                print_error "Unknown option: $1"
                show_usage
                exit 1
            fi
            ;;
    esac
done

# Main execution
print_header "🏷️  EMUSES Version Management"
print_header "=========================="

# Validate required parameters
if [ -z "$ACTION" ]; then
    print_error "Action is required"
    show_usage
    exit 1
fi

# Execute based on action
case $ACTION in
    list)
        list_versions
        ;;
    current)
        get_current_version
        ;;
    tag)
        if [ -z "$VERSION_TAG" ]; then
            print_error "Version tag is required"
            show_usage
            exit 1
        fi
        create_version_tag "$VERSION_TAG"
        ;;
    cleanup)
        cleanup_versions "$CLEANUP_KEEP"
        ;;
    info)
        if [ -z "$VERSION_TAG" ]; then
            print_error "Version tag is required"
            show_usage
            exit 1
        fi
        show_version_info "$VERSION_TAG"
        ;;
    *)
        print_error "Unknown action: $ACTION"
        show_usage
        exit 1
        ;;
esac

print_header "✅ VERSION MANAGEMENT COMPLETED"