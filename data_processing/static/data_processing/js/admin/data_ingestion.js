class DataIngestionPartitionManager {
    constructor() {
        this.ingestionId = this.getIngestionId();
        this.currentPage = 1;
        this.pageSize = 10;
        this.statusFilter = '';
        this.isLoading = false;
        this.setupUI();
    }

    getIngestionId() {
        // Get ingestion ID from URL or hidden input
        const urlMatch = window.location.pathname.match(/\/data_processing\/dataingestion\/(\d+)\//);
        if (urlMatch) return urlMatch[1];
        
        const input = document.querySelector('input[name="ingestion_id"]');
        return input ? input.value : null;
    }

    getFileName(path) {
        if (!path) return '-';
        // Clean the path and get the last segment
        const cleanPath = path.replace(/^\/media\//, '').split('/').pop();
        return cleanPath || '-';
    }

    getDownloadUrl(path) {
        if (!path) return null;
        // Ensure the path starts with /media/
        return path.startsWith('/media/') ? path : `/media/${path}`;
    }

    setupUI() {
        // Hide original table and create new container
        const originalTable = document.querySelector('.inline-group table');
        if (originalTable) originalTable.style.display = 'none';

        // Create loading overlay
        const loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loading-overlay';
        loadingOverlay.className = 'loading-overlay';
        loadingOverlay.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="loading-text">Loading...</div>
            </div>
        `;
        document.body.appendChild(loadingOverlay);

        // Create toast container for notifications
        const toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);

        // Create and insert new table container
        const container = document.createElement('div');
        container.className = 'data-ingestion-container';
        container.innerHTML = `
            <div class="controls">
                <div class="filter-group">
                    <div class="status-filter-group">
                        <div class="status-filter">
                            <label for="status-select">Status:</label>
                            <select id="status-select" class="form-select">
                                <option value="">All</option>
                                <option value="pending">Pending</option>
                                <option value="processing">Processing</option>
                                <option value="done">Done</option>
                                <option value="error">Error</option>
                            </select>
                        </div>
                        <button id="apply-filter" class="btn btn-primary" type="button">
                            <i class="fas fa-filter me-1"></i>Apply Filter
                        </button>
                    </div>
                    <div class="rows-per-page">
                        <label for="page-size-select">Rows per page:</label>
                        <select id="page-size-select" class="form-select">
                            <option value="10">10</option>
                            <option value="20">20</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                            <option value="500">500</option>
                        </select>
                    </div>
                </div>
                <div class="pagination-info">
                    <span>Total: <span id="total-count">0</span></span>
                </div>
            </div>
            <div class="table-responsive">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Partition ID</th>
                            <th>Input File</th>
                            <th>Status</th>
                            <th>Processed At</th>
                            <th>Error Message</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="partitions-table-body"></tbody>
                </table>
            </div>
            <div class="pagination">
                <button id="prev-page" class="btn btn-outline-secondary" type="button">&laquo; Previous</button>
                <span id="page-info" class="mx-3">Page 1</span>
                <button id="next-page" class="btn btn-outline-secondary" type="button">Next &raquo;</button>
            </div>
        `;

        originalTable.parentNode.insertBefore(container, originalTable);

        // Add event listeners
        const applyFilterBtn = document.getElementById('apply-filter');
        if (applyFilterBtn) {
            applyFilterBtn.addEventListener('click', async () => {
                this.currentPage = 1;  // Reset to first page when filter is applied
                await this.loadPartitions();
            });
        }

        // Add rows per page change listener
        const pageSizeSelect = document.getElementById('page-size-select');
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', async (e) => {
                this.pageSize = parseInt(e.target.value);
                this.currentPage = 1;  // Reset to first page when changing page size
                await this.loadPartitions();
            });
        }

        // Add pagination event listeners
        const prevPageBtn = document.getElementById('prev-page');
        const nextPageBtn = document.getElementById('next-page');

        if (prevPageBtn) {
            prevPageBtn.addEventListener('click', async () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    await this.loadPartitions();
                }
            });
        }

        if (nextPageBtn) {
            nextPageBtn.addEventListener('click', async () => {
                this.currentPage++;
                await this.loadPartitions();
            });
        }

        // Load initial data
        this.loadPartitions();
    }

    async loadPartitions() {
        try {
            this.setLoading(true);
            const statusFilter = document.getElementById('status-select').value;
            const pageSizeSelect = document.getElementById('page-size-select');
            
            const data = {
                request_id: this.ingestionId,
                page: this.currentPage,
                page_size: pageSizeSelect ? parseInt(pageSizeSelect.value) : this.pageSize
            };

            if (statusFilter) {
                data.status = statusFilter;
            }

            console.log('Fetching partitions for ingestion:', this.ingestionId);
            const response = await fetch('/api/v1/data-processing/data-ingestion/get-partitioned-files-list/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Failed to fetch partitions');
            }

            // Update total count
            const totalCountElement = document.getElementById('total-count');
            if (totalCountElement) {
                totalCountElement.textContent = result.total_count || 0;
            }

            // Clear existing rows
            const tableBody = document.getElementById('partitions-table-body');
            if (!tableBody) return;
            
            tableBody.innerHTML = '';

            // Add new rows
            result.results.forEach(partition => {
                const row = document.createElement('tr');
                
                // Add status class to row
                if (partition.status === 'error') {
                    row.classList.add('table-danger');
                } else if (partition.status === 'done') {
                    row.classList.add('table-success');
                } else if (partition.status === 'processing') {
                    row.classList.add('table-warning');
                }

                const inputFileUrl = this.getDownloadUrl(partition.input_file_path);

                row.innerHTML = `
                    <td>${partition.id}</td>
                    <td>
                        <div class="file-info" title="${partition.input_file_path || '-'}">
                            ${this.getFileName(partition.input_file_path)}
                            ${partition.input_file_path ? `<a href="/media/${partition.input_file_path}" download class="download-link"><i class="fas fa-download"></i></a>` : ''}
                        </div>
                    </td>
                    <td>
                        <select class="form-select status-select" data-partition-id="${partition.id}" data-original-status="${partition.status}">
                            <option value="pending" ${partition.status === 'pending' ? 'selected' : ''}>Pending</option>
                            <option value="processing" ${partition.status === 'processing' ? 'selected' : ''}>Processing</option>
                            <option value="done" ${partition.status === 'done' ? 'selected' : ''}>Done</option>
                            <option value="error" ${partition.status === 'error' ? 'selected' : ''}>Error</option>
                        </select>
                    </td>
                    <td>${partition.processed_at ? new Date(partition.processed_at).toLocaleString() : '-'}</td>
                    <td>${partition.error_message || '-'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary save-status" type="button">
                            <i class="fas fa-save"></i>
                            <span>Save</span>
                        </button>
                    </td>
                `;

                tableBody.appendChild(row);

                // Add event listeners to the newly created elements
                const statusSelect = row.querySelector('.status-select');
                const saveButton = row.querySelector('.save-status');

                if (statusSelect) {
                    statusSelect.addEventListener('change', (e) => this.handleStatusChange(e));
                }

                if (saveButton) {
                    saveButton.addEventListener('click', (e) => this.handleSaveStatus(e));
                }
            });

            // Update pagination
            this.updatePagination(result.total_count);

        } catch (error) {
            console.error('Error loading partitions:', error);
            this.showToast(`Failed to load partitions: ${error.message}`, 'error');
            
            const tableBody = document.getElementById('partitions-table-body');
            if (tableBody) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="text-center text-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            Failed to load data. Please try again later.
                        </td>
                    </tr>
                `;
            }
        } finally {
            this.setLoading(false);
        }
    }

    handleStatusChange(event) {
        const select = event.target;
        const row = select.closest('tr');
        const saveButton = row.querySelector('.save-status');
        const originalStatus = select.getAttribute('data-original-status');
        const newStatus = select.value;

        // Show/hide save button based on status change
        if (saveButton) {
            saveButton.style.display = originalStatus !== newStatus ? 'inline-flex' : 'none';
            // Disable the select while saving to prevent multiple changes
            saveButton.addEventListener('click', () => {
                select.disabled = true;
            });
        }
    }

    async handleSaveStatus(event) {
        const button = event.currentTarget;
        const row = button.closest('tr');
        const partitionId = row.querySelector('.status-select').getAttribute('data-partition-id');
        const newStatus = row.querySelector('.status-select').value;

        if (!partitionId || !newStatus) {
            this.showToast('Missing partition ID or status', 'error');
            return;
        }

        try {
            // Show loading state on button
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Saving...</span>';

            console.log('Updating partition status:', partitionId, 'to', newStatus);
            const response = await fetch('/api/v1/data-processing/data-ingestion/update-partition-status/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    partition_id: partitionId,
                    status: newStatus
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Failed to update status');
            }

            // Update the data-original-status attribute and hide the save button
            const statusSelect = row.querySelector('.status-select');
            statusSelect.setAttribute('data-original-status', newStatus);
            statusSelect.disabled = false;
            button.style.display = 'none';

            // Update row styling based on new status
            row.className = ''; // Clear existing classes
            if (newStatus === 'error') {
                row.classList.add('table-danger');
            } else if (newStatus === 'done') {
                row.classList.add('table-success');
            } else if (newStatus === 'processing') {
                row.classList.add('table-warning');
            }

            this.showToast('Status updated successfully', 'success');

        } catch (error) {
            console.error('Error updating status:', error);
            this.showToast(`Failed to update status: ${error.message}`, 'error');
            
            // Reset button state
            const statusSelect = row.querySelector('.status-select');
            statusSelect.disabled = false;
            
        } finally {
            // Reset button state
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-save"></i><span>Save</span>';
        }
    }

    updatePagination(totalCount) {
        const pageSize = this.pageSize;
        const totalPages = Math.ceil(totalCount / pageSize);
        
        const pageInfo = document.getElementById('page-info');
        if (pageInfo) {
            pageInfo.textContent = `Page ${this.currentPage} of ${totalPages || 1}`;
        }
        
        const prevButton = document.getElementById('prev-page');
        const nextButton = document.getElementById('next-page');
        
        if (prevButton) {
            prevButton.disabled = this.currentPage <= 1;
        }
        
        if (nextButton) {
            nextButton.disabled = this.currentPage >= totalPages;
        }
    }

    setLoading(isLoading) {
        this.isLoading = isLoading;
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = isLoading ? 'flex' : 'none';
        }
    }

    showToast(message, type = 'info') {
        const toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Set toast type styling
        let bgColor = '#17a2b8'; // info color
        let icon = 'info-circle';
        
        if (type === 'success') {
            bgColor = '#28a745';
            icon = 'check-circle';
        } else if (type === 'error') {
            bgColor = '#dc3545';
            icon = 'exclamation-circle';
        } else if (type === 'warning') {
            bgColor = '#ffc107';
            icon = 'exclamation-triangle';
        }
        
        toast.style.backgroundColor = bgColor;
        
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${icon} toast-icon"></i>
                <span>${message}</span>
            </div>
            <button class="toast-close">×</button>
        `;
        
        toastContainer.appendChild(toast);
        
        // Show toast with animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);
        
        // Auto close after 5 seconds
        const autoCloseTimeout = setTimeout(() => {
            this.closeToast(toast);
        }, 5000);
        
        // Add close button listener
        const closeButton = toast.querySelector('.toast-close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                clearTimeout(autoCloseTimeout);
                this.closeToast(toast);
            });
        }
    }
    
    closeToast(toast) {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300); // Wait for the animation to complete
    }

    getCsrfToken() {
        // Get CSRF token from cookie
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
            
        return cookieValue || '';
    }
}

// Initialize manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.inline-group')) {
        new DataIngestionPartitionManager();
    }
});

// Add CSS styles
document.addEventListener('DOMContentLoaded', () => {
    const styleSheet = document.createElement('style');
    styleSheet.textContent = `
        .data-ingestion-container {
            margin: 20px 0;
            padding: 0;
        }
        
        .controls {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: flex-end;
        }
        
        .status-filter-group {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }
        
        .status-filter, .rows-per-page {
            display: flex;
            flex-direction: column;
        }
        
        .form-select {
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ced4da;
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
            padding: 6px 12px;
            border-radius: 4px;
            border: 1px solid transparent;
            font-weight: 500;
        }
        
        .btn-primary {
            background-color: #007bff;
            color: white;
            border-color: #007bff;
        }
        
        .btn-outline-secondary {
            background-color: transparent;
            color: #6c757d;
            border-color: #6c757d;
        }
        
        .table {
            width: 100%;
            margin-bottom: 1rem;
            color: #212529;
            border-collapse: collapse;
        }
        
        .table th, .table td {
            padding: 0.75rem;
            vertical-align: middle;
            border-top: 1px solid #dee2e6;
        }
        
        .table thead th {
            vertical-align: bottom;
            border-bottom: 2px solid #dee2e6;
            background-color: #f8f9fa;
        }
        
        .table-success {
            background-color: #d4edda;
        }
        
        .table-danger {
            background-color: #f8d7da;
        }
        
        .table-warning {
            background-color: #fff3cd;
        }
        
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-top: 20px;
        }
        
        .file-info {
            display: flex;
            align-items: center;
            justify-content: space-between;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .download-link {
            margin-left: 10px;
            color: #007bff;
        }
        
        .error-message {
            color: #dc3545;
            font-size: 0.85em;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        /* Loading Overlay */
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        
        .loading-spinner {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
        }
        
        .loading-text {
            font-weight: bold;
        }
        
        /* Toast notifications */
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1050;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .toast {
            min-width: 250px;
            color: white;
            border-radius: 4px;
            padding: 12px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transform: translateX(120%);
            transition: transform 0.3s ease;
            opacity: 0.9;
        }
        
        .toast.show {
            transform: translateX(0);
        }
        
        .toast-content {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .toast-icon {
            font-size: 1.2em;
        }
        
        .toast-close {
            background: none;
            border: none;
            color: white;
            font-size: 20px;
            cursor: pointer;
            padding: 0;
            margin: 0;
            height: 24px;
            width: 24px;
            line-height: 24px;
            text-align: center;
        }
    `;
    document.head.appendChild(styleSheet);
});
