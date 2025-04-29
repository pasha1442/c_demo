class DataEnrichmentPartitionManager {
    constructor() {
        this.enrichmentId = this.getEnrichmentId();
        this.currentPage = 1;
        this.pageSize = 10;
        this.statusFilter = '';
        this.isLoading = false;
        this.setupUI();
    }

    getEnrichmentId() {
        // Get enrichment ID from URL or hidden input
        const urlMatch = window.location.pathname.match(/\/data_processing\/dataenrichment\/(\d+)\//);
        if (urlMatch) return urlMatch[1];
        
        const input = document.querySelector('input[name="enrichment_id"]');
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
        container.className = 'data-enrichment-container';
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
                            <th>Output File</th>
                            <th>Status</th>
                            <th>Processed At</th>
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
                enrichment_id: this.enrichmentId,
                page: this.currentPage,
                page_size: pageSizeSelect ? parseInt(pageSizeSelect.value) : this.pageSize
            };

            if (statusFilter) {
                data.status = statusFilter;
            }

            const response = await fetch('/api/v1/data-processing/data-enrichment/get-partitioned-files-list/', {
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

                const inputFileUrl = this.getDownloadUrl(partition.input_file);
                const outputFileUrl = this.getDownloadUrl(partition.output_file);

                row.innerHTML = `
                    <td>${partition.id}</td>
                    <td>
                        <div class="file-info" title="${partition.input_file || '-'}">
                            ${this.getFileName(partition.input_file)}
                            ${inputFileUrl ? `<a href="${inputFileUrl}" download class="download-link"><i class="fas fa-download"></i></a>` : ''}
                        </div>
                    </td>
                    <td>
                        <div class="file-info" title="${partition.output_file || '-'}">
                            ${this.getFileName(partition.output_file)}
                            ${outputFileUrl ? `<a href="${outputFileUrl}" download class="download-link"><i class="fas fa-download"></i></a>` : ''}
                        </div>
                    </td>
                    <td>
                        <select class="form-select status-select" data-partition-id="${partition.id}" data-original-status="${partition.status}">
                            <option value="pending" ${partition.status === 'pending' ? 'selected' : ''}>Pending</option>
                            <option value="processing" ${partition.status === 'processing' ? 'selected' : ''}>Processing</option>
                            <option value="done" ${partition.status === 'done' ? 'selected' : ''}>Done</option>
                            <option value="error" ${partition.status === 'error' ? 'selected' : ''}>Error</option>
                        </select>
                        ${partition.error_message ? `<div class="error-message mt-2">${partition.error_message}</div>` : ''}
                    </td>
                    <td>${partition.processed_at ? new Date(partition.processed_at).toLocaleString() : '-'}</td>
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
                saveButton.disabled = true;
            }, { once: true });
        }
    }

    async handleSaveStatus(event) {
        try {
            const button = event.target.closest('.save-status'); // Fix event target for icon clicks
            const row = button.closest('tr');
            const select = row.querySelector('.status-select');
            const partitionId = select.dataset.partitionId;
            const newStatus = select.value;

            this.setLoading(true);
            const response = await fetch('/api/v1/data-processing/data-enrichment/update-partition-status/', {
                method: 'PUT',  // Changed from POST to PUT
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    partition_id: partitionId,
                    status: newStatus
                })
            });

            const data = await response.json();

            if (!response.ok) {
                // Following our error handling patterns
                const errorType = response.status >= 500 ? 'critical' : 'non_critical';
                throw {
                    message: data.error || 'Failed to update status',
                    type: errorType,
                    raw_response: data
                };
            }

            // Update original status after successful save
            select.setAttribute('data-original-status', newStatus);
            button.style.display = 'none';  // Hide save button after successful update
            
            // Update row status class
            row.classList.remove('table-success', 'table-danger', 'table-warning');
            if (newStatus === 'error') {
                row.classList.add('table-danger');
            } else if (newStatus === 'done') {
                row.classList.add('table-success');
            } else if (newStatus === 'processing') {
                row.classList.add('table-warning');
            }

            // Re-enable the select after successful update
            select.disabled = false;
            button.disabled = false;

            this.showToast('Status updated successfully', 'success');
            
        } catch (error) {
            console.error('Error updating status:', error);
            // Following our established error handling patterns
            const errorMessage = error.type === 'critical' 
                ? 'A critical error occurred. Please try again later.' 
                : `Failed to update status: ${error.message}`;
            this.showToast(errorMessage, 'error');

            // Re-enable controls on error
            const select = event.target.closest('tr').querySelector('.status-select');
            const button = event.target.closest('.save-status');
            if (select) select.disabled = false;
            if (button) button.disabled = false;
        } finally {
            this.setLoading(false);
        }
    }

    updatePagination(totalCount) {
        const totalPages = Math.ceil(totalCount / this.pageSize);
        
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');
        const pageInfo = document.getElementById('page-info');

        if (prevBtn && nextBtn && pageInfo) {
            prevBtn.disabled = this.currentPage <= 1;
            nextBtn.disabled = this.currentPage >= totalPages;
            pageInfo.textContent = `Page ${this.currentPage} of ${totalPages} (${totalCount} items)`;
        }
    }

    setLoading(isLoading) {
        const overlay = document.getElementById('loading-overlay');
        const filterButton = document.getElementById('apply-filter');
        const statusSelect = document.getElementById('status-select');
        const prevButton = document.getElementById('prev-page');
        const nextButton = document.getElementById('next-page');

        if (overlay) {
            overlay.style.display = isLoading ? 'flex' : 'none';
        }

        // Disable controls during loading
        [filterButton, statusSelect, prevButton, nextButton].forEach(element => {
            if (element) {
                element.disabled = isLoading;
            }
        });
    }

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                ${type === 'error' ? '<i class="fas fa-exclamation-circle me-2"></i>' : ''}
                ${message}
            </div>
        `;

        const container = document.querySelector('.toast-container');
        if (container) {
            container.appendChild(toast);

            // Remove toast after 3 seconds
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    }

    formatDate(dateString) {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleString();
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
}

// Initialize the manager when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new DataEnrichmentPartitionManager();
});
