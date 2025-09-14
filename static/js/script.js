// Upload Modal Functions
function showUploadModal(subject = '', className = '', indexKey = '') {
    const modal = document.getElementById('uploadModal');
    
    // Load subjects and classes when modal opens
    loadSubjectsAndClasses();
    
    if (subject) {
        setTimeout(() => {
            const subjectSelect = document.getElementById('subject');
            subjectSelect.value = subject;
            onSubjectChange();
            if (className) {
                setTimeout(() => {
                    const classSelect = document.getElementById('class_name');
                    classSelect.value = className;
                    onClassChange();
                    if (indexKey) {
                        setTimeout(() => {
                            const indexSelect = document.getElementById('index_key');
                            indexSelect.value = indexKey;
                        }, 100);
                    }
                }, 100);
            }
        }, 100);
    }
    
    modal.style.display = 'block';
}

function closeUploadModal() {
    document.getElementById('uploadModal').style.display = 'none';
    document.getElementById('uploadForm').reset();
}

// Load subjects and classes for dropdowns
function loadSubjectsAndClasses() {
    fetch('/api/subjects')
        .then(response => response.json())
        .then(data => {
            populateSubjectDropdown(data);
        })
        .catch(error => {
            console.error('Error loading subjects:', error);
        });
}

function populateSubjectDropdown(subjects) {
    const subjectSelect = document.getElementById('subject');
    const classSelect = document.getElementById('class_name');
    const indexSelect = document.getElementById('index_key');
    
    // Clear existing options except the first one
    subjectSelect.innerHTML = '<option value="">Select a subject...</option>';
    classSelect.innerHTML = '<option value="">Select a subject first...</option>';
    indexSelect.innerHTML = '<option value="">Auto-detect from textbook index...</option>';
    
    // Populate subjects
    for (const [subjectName, subjectData] of Object.entries(subjects)) {
        const option = document.createElement('option');
        option.value = subjectName;
        option.textContent = subjectName;
        subjectSelect.appendChild(option);
    }
    
    // Add event listener for subject change
    subjectSelect.addEventListener('change', onSubjectChange);
    classSelect.addEventListener('change', onClassChange);
}

function onSubjectChange() {
    const subjectSelect = document.getElementById('subject');
    const classSelect = document.getElementById('class_name');
    const indexSelect = document.getElementById('index_key');
    const selectedSubject = subjectSelect.value;
    
    // Clear class and index dropdowns
    classSelect.innerHTML = '<option value="">Select a class...</option>';
    indexSelect.innerHTML = '<option value="">Auto-detect from textbook index...</option>';
    
    if (selectedSubject) {
        // Enable class dropdown
        classSelect.disabled = false;
        
        // Load classes for selected subject
        fetch('/api/subjects')
            .then(response => response.json())
            .then(data => {
                if (data[selectedSubject] && data[selectedSubject].classes) {
                    for (const [className, classData] of Object.entries(data[selectedSubject].classes)) {
                        const option = document.createElement('option');
                        option.value = className;
                        option.textContent = className;
                        classSelect.appendChild(option);
                    }
                }
            });
    } else {
        classSelect.disabled = true;
        indexSelect.disabled = true;
    }
}

function onClassChange() {
    const subjectSelect = document.getElementById('subject');
    const classSelect = document.getElementById('class_name');
    const indexSelect = document.getElementById('index_key');
    const selectedSubject = subjectSelect.value;
    const selectedClass = classSelect.value;
    
    // Clear index dropdown
    indexSelect.innerHTML = '<option value="">Auto-detect from textbook index...</option>';
    
    if (selectedSubject && selectedClass) {
        // Enable index dropdown
        indexSelect.disabled = false;
        
        // Load indices for selected class
        fetch(`/api/indices/${encodeURIComponent(selectedSubject)}/${encodeURIComponent(selectedClass)}`)
            .then(response => response.json())
            .then(data => {
                if (data.has_index && data.structure.length > 0) {
                    for (const item of data.structure) {
                        const option = document.createElement('option');
                        option.value = item.number || item.title.toLowerCase().replace(' ', '_');
                        option.textContent = `${item.number || ''} ${item.title}`.trim();
                        indexSelect.appendChild(option);
                    }
                } else {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = 'No textbook index uploaded - will auto-detect';
                    indexSelect.appendChild(option);
                }
            })
            .catch(error => {
                console.error('Error loading indices:', error);
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'Error loading indices - will auto-detect';
                indexSelect.appendChild(option);
            });
    } else {
        indexSelect.disabled = true;
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    const uploadModal = document.getElementById('uploadModal');
    const noteModal = document.getElementById('noteModal');
    
    if (event.target === uploadModal) {
        closeUploadModal();
    }
    if (event.target === noteModal) {
        closeNoteModal();
    }
}

// File Upload Handling
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validate form fields
            const subject = this.querySelector('#subject').value;
            const className = this.querySelector('#class_name').value;
            const file = this.querySelector('#file').files[0];
            
            if (!subject) {
                showNotification('Please select a subject', 'error');
                return;
            }
            
            if (!className) {
                showNotification('Please select a class', 'error');
                return;
            }
            
            if (!file) {
                showNotification('Please select a file to upload', 'error');
                return;
            }
            
            // Validate file
            if (!validateFile(file)) {
                return;
            }
            
            const formData = new FormData(this);
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            
            // Show loading state
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
            submitBtn.disabled = true;
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Show success message
                    showNotification('Note uploaded and analyzed successfully!', 'success');
                    
                    // Close modal and reset form
                    closeUploadModal();
                    
                    // Reload the current page to show new note
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else {
                    throw new Error(data.error || 'Upload failed');
                }
            })
            .catch(error => {
                console.error('Upload error:', error);
                showNotification('Error uploading note: ' + error.message, 'error');
            })
            .finally(() => {
                // Reset button state
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    }
});

// Note Actions
function starNote(noteId) {
    // TODO: Implement starring functionality
    showNotification('Note starred!', 'success');
}

function highlightNote(noteId) {
    // TODO: Implement highlighting functionality
    showNotification('Note highlighted!', 'success');
}

function questionNote(noteId) {
    // TODO: Implement question marking functionality
    showNotification('Note marked for questions!', 'success');
}

// View Note Details
function viewNote(noteId) {
    fetch(`/api/note/${noteId}`)
        .then(response => response.json())
        .then(note => {
            displayNoteModal(note);
        })
        .catch(error => {
            console.error('Error loading note:', error);
            showNotification('Error loading note details', 'error');
        });
}

function displayNoteModal(note) {
    const modal = document.getElementById('noteModal');
    const title = document.getElementById('noteTitle');
    const content = document.getElementById('noteContent');
    const analysis = document.getElementById('noteAnalysis');
    
    title.textContent = note.original_name;
    content.innerHTML = `<pre>${escapeHtml(note.content)}</pre>`;
    
    // Display AI analysis
    const aiData = note.ai_analysis || {};
    let analysisHtml = '<div class="ai-analysis">';
    
    if (aiData.key_topics && aiData.key_topics.length > 0) {
        analysisHtml += '<h4><i class="fas fa-tags"></i> Key Topics</h4><ul>';
        aiData.key_topics.forEach(topic => {
            analysisHtml += `<li>${escapeHtml(topic)}</li>`;
        });
        analysisHtml += '</ul>';
    }
    
    if (aiData.important_equations && aiData.important_equations.length > 0) {
        analysisHtml += '<h4><i class="fas fa-calculator"></i> Important Equations</h4><ul>';
        aiData.important_equations.forEach(eq => {
            analysisHtml += `<li><code>${escapeHtml(eq)}</code></li>`;
        });
        analysisHtml += '</ul>';
    }
    
    if (aiData.highlights && aiData.highlights.length > 0) {
        analysisHtml += '<h4><i class="fas fa-highlighter"></i> AI Highlights</h4><ul>';
        aiData.highlights.forEach(highlight => {
            analysisHtml += `<li class="highlight-item">${escapeHtml(highlight)}</li>`;
        });
        analysisHtml += '</ul>';
    }
    
    if (aiData.test_questions && aiData.test_questions.length > 0) {
        analysisHtml += '<h4><i class="fas fa-question-circle"></i> Test Questions</h4><ul>';
        aiData.test_questions.forEach(question => {
            analysisHtml += `<li>${escapeHtml(question)}</li>`;
        });
        analysisHtml += '</ul>';
    }
    
    if (aiData.related_links && aiData.related_links.length > 0) {
        analysisHtml += '<h4><i class="fas fa-link"></i> Related Concepts</h4><ul>';
        aiData.related_links.forEach(link => {
            analysisHtml += `<li>${escapeHtml(link)}</li>`;
        });
        analysisHtml += '</ul>';
    }
    
    if (aiData.error) {
        analysisHtml += '<div class="error-message"><i class="fas fa-exclamation-triangle"></i> AI Analysis Error: ' + escapeHtml(aiData.error) + '</div>';
    }
    
    analysisHtml += '</div>';
    analysis.innerHTML = analysisHtml;
    
    modal.style.display = 'block';
}

function closeNoteModal() {
    document.getElementById('noteModal').style.display = 'none';
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#48bb78' : type === 'error' ? '#f56565' : '#4299e1'};
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 500;
        animation: slideInRight 0.3s ease-out;
    `;
    
    // Add animation keyframes if not already added
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideInRight {
                from {
                    opacity: 0;
                    transform: translateX(100%);
                }
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }
            @keyframes slideOutRight {
                from {
                    opacity: 1;
                    transform: translateX(0);
                }
                to {
                    opacity: 0;
                    transform: translateX(100%);
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(notification);
    
    // Remove notification after 4 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 4000);
}

// Search functionality (placeholder)
function searchNotes() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    // TODO: Implement search functionality
    showNotification('Search functionality coming soon!', 'info');
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Escape key closes modals
    if (e.key === 'Escape') {
        closeUploadModal();
        closeNoteModal();
    }
    
    // Ctrl/Cmd + U opens upload modal
    if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
        e.preventDefault();
        showUploadModal();
    }
});

// Initialize tooltips for interactive elements
document.addEventListener('DOMContentLoaded', function() {
    // Add hover effects for interactive elements
    const interactiveElements = document.querySelectorAll('.note-card, .subject-card, .class-card, .action-card');
    
    interactiveElements.forEach(element => {
        element.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        element.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // Add loading animation for async operations
    window.showLoading = function(element) {
        element.style.opacity = '0.6';
        element.style.pointerEvents = 'none';
    };
    
    window.hideLoading = function(element) {
        element.style.opacity = '1';
        element.style.pointerEvents = 'auto';
    };
});

// Error handling for fetch requests
function handleFetchError(error, operation = 'operation') {
    console.error(`${operation} error:`, error);
    showNotification(`Error during ${operation}. Please try again.`, 'error');
}

// File validation
function validateFile(file) {
    const allowedTypes = ['.txt', '.md', '.docx', '.pdf'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(fileExtension)) {
        showNotification('Please upload a valid file (.txt, .md, .docx, .pdf)', 'error');
        return false;
    }
    
    if (file.size > 16 * 1024 * 1024) { // 16MB
        showNotification('File size must be less than 16MB', 'error');
        return false;
    }
    
    return true;
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load subjects and classes when the page loads
    loadSubjectsAndClasses();
    
    // Add error handling for fetch requests
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        return originalFetch.apply(this, args)
            .catch(error => {
                console.error('Fetch error:', error);
                showNotification('Network error. Please check your connection.', 'error');
                throw error;
            });
    };
    
    // Add file validation to upload form
    const fileInput = document.getElementById('file');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file && !validateFile(file)) {
                e.target.value = ''; // Clear the file input
            }
        });
    }
});
