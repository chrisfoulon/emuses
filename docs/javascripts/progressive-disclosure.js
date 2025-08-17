/**
 * Progressive Disclosure Enhancement for EMUSES Documentation
 * Adds expand/collapse all functionality for details elements
 */

document.addEventListener('DOMContentLoaded', function() {
    // Only add toggle functionality if details elements exist
    const detailsElements = document.querySelectorAll('details');
    if (detailsElements.length === 0) {
        return;
    }

    // Add expand/collapse all button
    function addToggleButton() {
        const button = document.createElement('button');
        button.textContent = 'Expand All Sections';
        button.className = 'md-button md-button--primary progressive-disclosure-toggle';
        button.style.cssText = `
            margin: 1rem 0;
            background-color: var(--md-primary-fg-color);
            color: var(--md-primary-bg-color);
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.25rem;
            cursor: pointer;
            font-size: 0.875rem;
            font-weight: 500;
            transition: all 0.2s ease;
        `;
        
        let expanded = false;
        
        // Toggle functionality
        button.addEventListener('click', () => {
            const details = document.querySelectorAll('details');
            details.forEach(detail => {
                detail.open = !expanded;
            });
            expanded = !expanded;
            button.textContent = expanded ? 'Collapse All Sections' : 'Expand All Sections';
        });

        // Hover effect
        button.addEventListener('mouseenter', () => {
            button.style.opacity = '0.9';
            button.style.transform = 'translateY(-1px)';
        });

        button.addEventListener('mouseleave', () => {
            button.style.opacity = '1';
            button.style.transform = 'translateY(0)';
        });
        
        // Insert after the main heading or description
        const insertTarget = document.querySelector('h1') || document.querySelector('.md-content h1');
        if (insertTarget) {
            // Find the next sibling that's not a heading to insert after description
            let insertAfter = insertTarget;
            let nextElement = insertTarget.nextElementSibling;
            
            // Look for description paragraph or horizontal rule
            while (nextElement && (nextElement.tagName === 'P' || nextElement.tagName === 'HR')) {
                insertAfter = nextElement;
                nextElement = nextElement.nextElementSibling;
            }
            
            insertAfter.parentNode.insertBefore(button, insertAfter.nextSibling);
        }
    }

    // Track user interactions for UX analytics
    function trackDisclosureUsage() {
        const details = document.querySelectorAll('details');
        details.forEach((detail, index) => {
            detail.addEventListener('toggle', () => {
                // Could be extended for analytics if needed
                console.debug(`Details section ${index} ${detail.open ? 'expanded' : 'collapsed'}`);
            });
        });
    }

    // Initialize enhancements
    addToggleButton();
    trackDisclosureUsage();

    // Add accessibility improvements
    function enhanceAccessibility() {
        const summaryElements = document.querySelectorAll('details summary');
        summaryElements.forEach(summary => {
            // Ensure proper ARIA attributes
            if (!summary.getAttribute('role')) {
                summary.setAttribute('role', 'button');
            }
            if (!summary.getAttribute('aria-expanded')) {
                summary.setAttribute('aria-expanded', summary.parentElement.open ? 'true' : 'false');
            }
            
            // Update aria-expanded when toggled
            summary.parentElement.addEventListener('toggle', () => {
                summary.setAttribute('aria-expanded', summary.parentElement.open ? 'true' : 'false');
            });
        });
    }

    enhanceAccessibility();
});

/**
 * Add visual indicators for progressive disclosure sections
 */
function addVisualIndicators() {
    const style = document.createElement('style');
    style.textContent = `
        /* Progressive disclosure visual enhancements */
        details summary {
            cursor: pointer;
            padding: 0.5rem 0;
            border-radius: 0.25rem;
            transition: background-color 0.2s ease;
        }
        
        details summary:hover {
            background-color: var(--md-default-bg-color--light);
        }
        
        details summary::before {
            content: "▶";
            display: inline-block;
            margin-right: 0.5rem;
            transition: transform 0.2s ease;
            font-size: 0.875em;
        }
        
        details[open] summary::before {
            transform: rotate(90deg);
        }
        
        details summary strong {
            font-weight: 600;
        }
        
        /* Nested details styling */
        details details {
            margin-left: 1rem;
            border-left: 2px solid var(--md-default-fg-color--lighter);
            padding-left: 1rem;
        }
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {
            .progressive-disclosure-toggle {
                width: 100%;
                margin: 0.5rem 0;
            }
        }
    `;
    
    document.head.appendChild(style);
}

// Apply visual indicators immediately
addVisualIndicators();