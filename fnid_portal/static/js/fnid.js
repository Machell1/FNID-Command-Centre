/* =================================================================
   FNID Area 3 Operational Portal - Frontend JavaScript
   ================================================================= */

document.addEventListener('DOMContentLoaded', function() {

    if (window.jQuery && $.fn.dataTable) {
        $.fn.dataTable.ext.errMode = function(settings, techNote, message) {
            if (window.console && console.warn) {
                console.warn('DataTables warning:', message);
            }
        };
    }

    function removeDataTablePlaceholderRows(table) {
        table.querySelectorAll('tbody tr').forEach(function(row) {
            var cells = row.querySelectorAll('td, th');
            if (cells.length === 1 && cells[0].hasAttribute('colspan')) {
                row.remove();
            }
        });
    }

    // Initialize DataTables on all tables with .fnid-table class
    document.querySelectorAll('.fnid-table').forEach(function(table) {
        // DataTables cannot parse placeholder tbody rows that use colspan.
        // Let DataTables render its own configured empty-table message instead.
        removeDataTablePlaceholderRows(table);

        if (table.dataset.datatableManual === 'true') return;
        if (!window.jQuery || !$.fn.DataTable) return;
        if ($.fn.DataTable.isDataTable(table)) return;

        var orderColumn = parseInt(table.dataset.datatableOrderColumn || '0', 10);
        var orderDirection = table.dataset.datatableOrderDirection || 'desc';
        var searchLabel = table.dataset.datatableSearchLabel || 'Search records:';
        var emptyTable = table.dataset.datatableEmpty || "No records found. Click 'New Entry' to add.";

        $(table).DataTable({
            pageLength: 25,
            order: [[orderColumn, orderDirection]],
            responsive: true,
            dom: '<"row"<"col-sm-6"l><"col-sm-6"f>>rtip',
            language: {
                search: searchLabel,
                lengthMenu: "Show _MENU_ records",
                info: "Showing _START_ to _END_ of _TOTAL_ records",
                emptyTable: emptyTable,
            }
        });
    });

    // Auto-calculate 48-hour deadline from arrest date/time
    var arrestDate = document.getElementById('arrest_date');
    var arrestTime = document.getElementById('arrest_time');
    var deadline = document.getElementById('deadline_48hr');
    if (arrestDate && arrestTime && deadline) {
        function calc48hr() {
            if (arrestDate.value && arrestTime.value) {
                var dt = new Date(arrestDate.value + 'T' + arrestTime.value);
                dt.setHours(dt.getHours() + 48);
                deadline.value = dt.toISOString().slice(0, 16).replace('T', ' ');
            }
        }
        arrestDate.addEventListener('change', calc48hr);
        arrestTime.addEventListener('change', calc48hr);
    }

    // Form validation enhancement
    document.querySelectorAll('form.needs-validation').forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                // Scroll to first invalid field
                var firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus();
                }
            }
            form.classList.add('was-validated');
        });
    });

    // Confirmation for submit action
    document.querySelectorAll('.btn-submit-record').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            if (!confirm('Submit this record? Once submitted, changes will be tracked in the audit log.')) {
                e.preventDefault();
            }
        });
    });

    // Status badge coloring
    document.querySelectorAll('[data-status]').forEach(function(el) {
        var status = el.getAttribute('data-status').toLowerCase();
        if (status.includes('draft'))      el.classList.add('badge-draft');
        else if (status.includes('submitted')) el.classList.add('badge-submitted');
        else if (status.includes('edited'))    el.classList.add('badge-edited');
        else if (status.includes('approved'))  el.classList.add('badge-approved');
        else if (status.includes('rejected'))  el.classList.add('badge-rejected');
    });

    // SOP checklist progress calculation
    var sopForm = document.getElementById('sop-checklist-form');
    if (sopForm) {
        function updateProgress() {
            var checks = sopForm.querySelectorAll('select.sop-check');
            var total = checks.length;
            var done = 0;
            checks.forEach(function(sel) {
                if (sel.value === 'Yes') done++;
            });
            var pct = total > 0 ? Math.round((done / total) * 100) : 0;
            var bar = document.getElementById('sop-progress-bar');
            var label = document.getElementById('sop-progress-label');
            if (bar) {
                bar.style.width = pct + '%';
                bar.setAttribute('aria-valuenow', pct);
                bar.className = 'progress-bar';
                if (pct >= 90) bar.classList.add('bg-success');
                else if (pct >= 60) bar.classList.add('bg-warning');
                else bar.classList.add('bg-danger');
            }
            if (label) label.textContent = pct + '% Complete (' + done + '/' + total + ')';
        }
        sopForm.querySelectorAll('select.sop-check').forEach(function(sel) {
            sel.addEventListener('change', updateProgress);
        });
        updateProgress();
    }

    // Chart rendering helper
    window.fnidChart = function(canvasId, type, labels, datasets, options) {
        var ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        var defaults = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: type === 'pie' || type === 'doughnut' ? 'right' : 'top',
                    labels: { font: { size: 11 } }
                }
            }
        };
        return new Chart(ctx, {
            type: type,
            data: { labels: labels, datasets: datasets },
            options: Object.assign(defaults, options || {})
        });
    };

    // Delete confirmation for destructive actions
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
        el.addEventListener('click', function(e) {
            if (!confirm(el.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

    // Auto-dismiss flash messages after 8 seconds
    document.querySelectorAll('.alert[role="alert"]').forEach(function(alert) {
        if (alert.querySelector('.btn-close')) {
            setTimeout(function() {
                try {
                    var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                    if (bsAlert) bsAlert.close();
                } catch(err) {}
            }, 8000);
        }
    });

    // ===================================================================
    // KEYBOARD SHORTCUTS
    // ===================================================================
    document.addEventListener('keydown', function(e) {
        var activeTag = document.activeElement ? document.activeElement.tagName : '';
        var isInput = activeTag === 'INPUT' || activeTag === 'TEXTAREA' || activeTag === 'SELECT';

        // Ctrl+K: Focus search bar
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            var search = document.getElementById('global-search');
            if (search) {
                search.focus();
                search.select();
            }
        }

        // Only process remaining shortcuts when not in a text input
        if (isInput) return;

        // ?: Open help modal
        if (e.key === '?' && !e.ctrlKey && !e.altKey) {
            e.preventDefault();
            var helpModal = document.getElementById('helpModal');
            if (helpModal) {
                var modal = bootstrap.Modal.getOrCreateInstance(helpModal);
                modal.toggle();
            }
        }

        // Alt+H: Go home
        if (e.altKey && e.key === 'h') {
            e.preventDefault();
            window.location.href = '/';
        }

        // Alt+N: New case intake
        if (e.altKey && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/cases/intake';
        }

        // Alt+D: Command dashboard
        if (e.altKey && e.key === 'd') {
            e.preventDefault();
            window.location.href = '/command';
        }

        // Ctrl+Home: Scroll to top
        if (e.ctrlKey && e.key === 'Home') {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    // ===================================================================
    // BACK TO TOP BUTTON
    // ===================================================================
    var backToTopBtn = document.getElementById('back-to-top');
    if (backToTopBtn) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 300) {
                backToTopBtn.classList.remove('d-none');
            } else {
                backToTopBtn.classList.add('d-none');
            }
        });
        backToTopBtn.addEventListener('click', function() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // ===================================================================
    // UNSAVED CHANGES WARNING
    // ===================================================================
    var trackedForms = document.querySelectorAll('form[data-track-changes], form.track-changes');
    trackedForms.forEach(function(form) {
        var initialData = new FormData(form);
        var initialValues = {};
        initialData.forEach(function(value, key) {
            initialValues[key] = value;
        });

        var indicator = document.createElement('div');
        indicator.className = 'form-unsaved-indicator';
        indicator.innerHTML = '<i class="bi bi-exclamation-circle"></i> You have unsaved changes';
        document.body.appendChild(indicator);

        var hasChanges = false;

        function checkChanges() {
            var currentData = new FormData(form);
            var changed = false;
            currentData.forEach(function(value, key) {
                if (initialValues[key] !== undefined && initialValues[key] !== value) {
                    changed = true;
                }
            });
            hasChanges = changed;
            if (changed) {
                indicator.classList.add('show');
            } else {
                indicator.classList.remove('show');
            }
        }

        form.addEventListener('input', checkChanges);
        form.addEventListener('change', checkChanges);

        form.addEventListener('submit', function() {
            hasChanges = false;
            indicator.classList.remove('show');
        });

        window.addEventListener('beforeunload', function(e) {
            if (hasChanges) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    });

    // ===================================================================
    // FORM SUBMIT LOADING STATE
    // ===================================================================
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            var submitBtn = form.querySelector('[type="submit"]');
            if (submitBtn && !submitBtn.classList.contains('no-loading')) {
                submitBtn.classList.add('btn-loading');
                submitBtn.disabled = true;
                // Re-enable after 10 seconds in case of error
                setTimeout(function() {
                    submitBtn.classList.remove('btn-loading');
                    submitBtn.disabled = false;
                }, 10000);
            }
        });
    });

    // ===================================================================
    // PASSWORD VISIBILITY TOGGLE
    // ===================================================================
    document.querySelectorAll('.password-toggle').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var input = btn.closest('.input-group').querySelector('input');
            var icon = btn.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('bi-eye');
                icon.classList.add('bi-eye-slash');
                btn.setAttribute('aria-label', 'Hide password');
            } else {
                input.type = 'password';
                icon.classList.remove('bi-eye-slash');
                icon.classList.add('bi-eye');
                btn.setAttribute('aria-label', 'Show password');
            }
        });
    });

    // ===================================================================
    // INLINE FORM VALIDATION FEEDBACK
    // ===================================================================
    document.querySelectorAll('.form-control[required], .form-select[required]').forEach(function(field) {
        field.addEventListener('blur', function() {
            if (field.value.trim() === '') {
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
                field.classList.add('is-valid');
            }
        });
        field.addEventListener('input', function() {
            if (field.value.trim() !== '') {
                field.classList.remove('is-invalid');
                field.classList.add('is-valid');
            }
        });
    });

    // ===================================================================
    // TOOLTIP INITIALIZATION
    // ===================================================================
    var tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(function(el) {
        new bootstrap.Tooltip(el);
    });

    // ===================================================================
    // SESSION TIMEOUT WARNING
    // ===================================================================
    var sessionTimeoutMinutes = 60 * 8; // 8-hour session
    var warningMinutes = 10;
    var sessionWarningTimeout = setTimeout(function() {
        var toast = document.createElement('div');
        toast.className = 'position-fixed bottom-0 end-0 p-3';
        toast.style.zIndex = '1055';
        toast.innerHTML =
            '<div class="toast show align-items-center text-bg-warning border-0" role="alert" aria-live="assertive">' +
            '  <div class="d-flex">' +
            '    <div class="toast-body">' +
            '      <i class="bi bi-clock-history me-1"></i> Your session will expire in ' + warningMinutes + ' minutes. Save your work.' +
            '    </div>' +
            '    <button type="button" class="btn-close btn-close-dark me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
            '  </div>' +
            '</div>';
        document.body.appendChild(toast);
    }, (sessionTimeoutMinutes - warningMinutes) * 60 * 1000);

});
