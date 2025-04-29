(function($) {
    $ = $ || django.jQuery;
    
    $(document).ready(function() {
        const labelSelectionSection = $('.field-labels').closest('fieldset');
        const embeddingGroupsField = $('#id_embedding_groups');
        
        let embeddingGroups = {};
        
        function initializeEmbeddingGroups() {
            const groupsValue = embeddingGroupsField.val();
            if (groupsValue && groupsValue.trim() !== '') {
                try {
                    let cleanValue = groupsValue.trim();
                    
                    cleanValue = cleanValue.replace(/^[^{]*({.*?})[^}]*$/, '$1');
                    
                    cleanValue = cleanValue.replace(/'/g, '"');
                    
                    embeddingGroups = JSON.parse(cleanValue);
                    
                    console.log("Initialized embedding groups:", embeddingGroups);
                } catch (e) {
                    console.error("Error parsing embedding groups JSON:", e);
                    console.log("Problematic JSON string:", groupsValue);
                    
                    try {
                        const matches = groupsValue.match(/\{[^}]+\}/g);
                        if (matches && matches.length > 0) {
                            embeddingGroups = JSON.parse(matches[0].replace(/'/g, '"'));
                        } else {
                            embeddingGroups = {};
                        }
                    } catch (extractError) {
                        console.error("Failed to extract embedding data:", extractError);
                        embeddingGroups = {};
                    }
                }
            } else {
                embeddingGroups = {};
            }
        }
        
        function extractEmbeddingData(str) {
            const result = {};
            
            const labelMatch = str.match(/'([^']+)':/);
            if (!labelMatch) return null;
            
            const label = labelMatch[1];
            result[label] = {};
            
            const groupMatches = str.matchAll(/'([^']+_embedding)':\s*\[(.*?)\]/g);
            for (const match of groupMatches) {
                const groupName = match[1];
                const propsList = match[2];
                
                const props = propsList.split(',')
                    .map(p => p.trim().replace(/^'|'$/g, ''))
                    .filter(p => p);
                    
                result[label][groupName] = props;
            }
            
            return Object.keys(result[label]).length > 0 ? result : null;
        }
        
        function cleanupEmbeddingGroups() {
            Object.keys(embeddingGroups).forEach(label => {
                const validGroups = {};
                const groupNames = Object.keys(embeddingGroups[label]);
                
                groupNames.forEach(groupName => {
                    let isPartialOfLongerName = false;
                    
                    groupNames.forEach(otherName => {
                        if (otherName !== groupName && 
                            otherName.startsWith(groupName.substring(0, groupName.length-10)) && 
                            otherName.length > groupName.length) {
                            isPartialOfLongerName = true;
                        }
                    });
                    
                    if (!isPartialOfLongerName) {
                        validGroups[groupName] = embeddingGroups[label][groupName];
                    }
                });
                
                embeddingGroups[label] = validGroups;
            });
            
            updateEmbeddingGroupsField();
        }
        
        function updateEmbeddingGroupsField() {
            embeddingGroupsField.val(JSON.stringify(embeddingGroups, null, 2));
            console.log("Updated embedding groups field:", embeddingGroupsField.val());
        }
        
        function fetchLabels() {
            const labelsContainer = $('.field-labels .label-checkbox-list');
            
            labelsContainer.html('<p>Loading labels from Neo4j...</p>');
            
            const urlParts = window.location.pathname.split('/');
            const appName = urlParts[urlParts.indexOf('data_processing') >= 0 ? urlParts.indexOf('data_processing') : 2];
            const modelName = 'dataembedding';
            
            const fetchUrl = `/admin/${appName}/${modelName}/fetch_neo4j_labels/`;
            
            const csrftoken = getCookie('csrftoken');
            
            console.log("Fetching Labels - URL:", fetchUrl);
            
            $.ajax({
                url: fetchUrl,
                type: 'POST',
                data: {
                    csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()
                },
                headers: {
                    'X-CSRFToken': csrftoken
                },
                success: function(response) {
                    console.log("Labels Fetch Response:", response);
                    
                    if (response.success) {
                        labelsContainer.empty();
                        
                        window.neo4jLabelsWithProps = {};
                        
                        response.labels.forEach(function(labelData) {
                            const label = labelData.name;
                            const properties = labelData.properties;
                            
                            window.neo4jLabelsWithProps[label] = properties;
                            
                            const labelId = `id_label_${label.replace(/[^a-zA-Z0-9]/g, '_')}`;
                            const checkbox = $(`
                                <div class="checkbox-row">
                                    <input type="checkbox" name="labels" value="${label}" id="${labelId}" class="label-checkbox">
                                    <label for="${labelId}">${label} (${properties.length} properties)</label>
                                    <div class="property-group-container" id="group_container_${labelId}" style="display: none; margin-left: 20px;"></div>
                                </div>
                            `);
                            
                            labelsContainer.append(checkbox);
                        });
                        
                        $('.label-checkbox').change(function() {
                            const label = $(this).val();
                            const labelId = $(this).attr('id');
                            const groupContainer = $(`#group_container_${labelId}`);
                            
                            if ($(this).is(':checked')) {
                                fetchLabelProperties(label, groupContainer);
                            } else {
                                groupContainer.hide();
                                
                                if (embeddingGroups[label]) {
                                    delete embeddingGroups[label];
                                    updateEmbeddingGroupsField();
                                }
                            }
                        });
                        
                        initializeSelectedLabels();
                    } else {
                        labelsContainer.html(`<p class="error">Error loading labels: ${response.error}</p>`);
                        console.error("Labels fetch failed:", response.error);
                    }
                },
                error: function(xhr, status, error) {
                    labelsContainer.html(`<p class="error">Error loading labels: ${error}</p>`);
                    console.error("AJAX error:", xhr.responseText);
                    console.error("Status:", status);
                    console.error("Error:", error);
                }
            });
        }
        
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
        
        function fetchLabelProperties(label, container) {
            container.html('<p>Loading properties...</p>').show();
            
            if (window.neo4jLabelsWithProps && window.neo4jLabelsWithProps[label]) {
                displayPropertyGroups(label, window.neo4jLabelsWithProps[label], container);
                return;
            }
            
            const urlParts = window.location.pathname.split('/');
            const appName = urlParts[urlParts.indexOf('data_processing') >= 0 ? urlParts.indexOf('data_processing') : 2];
            const modelName = 'dataembedding';
            
            const fetchUrl = `/admin/${appName}/${modelName}/fetch_label_properties/${label}/`;
            
            const csrftoken = getCookie('csrftoken');
            
            $.ajax({
                url: fetchUrl,
                type: 'GET',
                headers: {
                    'X-CSRFToken': csrftoken
                },
                success: function(response) {
                    if (response.success) {
                        if (!window.neo4jLabelsWithProps) {
                            window.neo4jLabelsWithProps = {};
                        }
                        window.neo4jLabelsWithProps[label] = response.properties;
                        
                        displayPropertyGroups(label, response.properties, container);
                    } else {
                        container.html(`<p class="error">Error loading properties: ${response.error}</p>`);
                    }
                },
                error: function(xhr, status, error) {
                    container.html(`<p class="error">Error loading properties: ${error}</p>`);
                    console.error("AJAX error:", xhr.responseText);
                }
            });
        }
        
        function initializeSelectedLabels() {
            initializeEmbeddingGroups();
            cleanupEmbeddingGroups();
            
            console.log("Initialized Embedding Groups:", embeddingGroups);
            
            Object.keys(embeddingGroups).forEach(function(label) {
                const checkbox = $(`.label-checkbox[value="${label}"]`);
                if (checkbox.length) {
                    checkbox.prop('checked', true);
                    
                    const labelId = checkbox.attr('id');
                    const groupContainer = $(`#group_container_${labelId}`);
                    fetchLabelProperties(label, groupContainer);
                } else {
                    console.log(`Checkbox for label ${label} not found in the DOM`);
                }
            });
            
            const selectedLabels = [];
            
            try {
                if ($('#id_labels').prop('multiple')) {
                    $('#id_labels option:selected').each(function() {
                        selectedLabels.push($(this).val());
                    });
                } 
                else {
                    $('input[name="labels"]:checked').each(function() {
                        selectedLabels.push($(this).val());
                    });
                }
            } catch (e) {
                console.error("Error getting selected labels:", e);
            }
            
            console.log("Selected Labels:", selectedLabels);
            
            selectedLabels.forEach(function(label) {
                const checkbox = $(`.label-checkbox[value="${label}"]`);
                if (checkbox.length && !checkbox.is(':checked')) {
                    checkbox.prop('checked', true);
                    
                    const labelId = checkbox.attr('id');
                    const groupContainer = $(`#group_container_${labelId}`);
                    fetchLabelProperties(label, groupContainer);
                }
            });
        }
        
        function displayPropertyGroups(label, properties, container) {
            container.empty();
            
            const existingGroups = embeddingGroups[label] || {};
            
            container.append(`<p class="group-header"><strong>Embedding Groups for ${label}</strong></p>`);
            
            const addGroupBtn = $(`
                <button type="button" class="add-group-btn btn btn-primary btn-sm">
                    <i class="fa fa-plus"></i> Add Embedding Group
                </button>
            `);
            
            const groupsContainer = $('<div class="embedding-groups"></div>');
            container.append(addGroupBtn);
            container.append(groupsContainer);
            
            function addNewGroup(groupName = '', selectedProps = [], originalGroupName = null) {
                const groupId = `group_${label}_${Date.now()}`;
                
                const dataOriginalName = originalGroupName || (groupName ? groupName + '' : '');
                
                const group = $(`
                    <div class="embedding-group" id="${groupId}" data-original-name="${dataOriginalName}">
                        <div class="group-header">
                            <div class="group-name-container">
                                <label>Group Name:</label>
                                <input type="text" class="group-name-input form-control" 
                                       value="${groupName}" placeholder="e.g., category">
                            </div>
                            <div class="group-actions">
                                <button type="button" class="select-all-props btn btn-outline-secondary btn-sm">Select All</button>
                                <button type="button" class="select-none-props btn btn-outline-secondary btn-sm">Select None</button>
                                <button type="button" class="remove-group btn btn-danger btn-sm">
                                    <i class="fa fa-trash"></i> Remove Group
                                </button>
                            </div>
                        </div>
                        <div class="properties-list"></div>
                    </div>
                `);
                
                groupsContainer.append(group);
                
                const propertiesList = group.find('.properties-list');
                properties.forEach(function(property) {
                    const propId = `id_property_${groupId}_${property}`.replace(/[^a-zA-Z0-9]/g, '_');
                    const isChecked = selectedProps.includes(property);
                    
                    const propCheckbox = $(`
                        <div class="checkbox-row">
                            <input type="checkbox" name="property_${groupId}_${property}" value="${property}" 
                                   id="${propId}" class="property-checkbox" data-group="${groupId}" 
                                   data-label="${label}" ${isChecked ? 'checked' : ''}>
                            <label for="${propId}">${property}</label>
                        </div>
                    `);
                    
                    propertiesList.append(propCheckbox);
                });
                
                const groupNameInput = group.find('.group-name-input');
                
                groupNameInput.on('input', function() {
                    updateGroupInModel(label, groupId);
                });
                
                group.find('.property-checkbox').change(function() {
                    updateGroupInModel(label, groupId);
                });
                
                group.find('.select-all-props').click(function(e) {
                    e.preventDefault();
                    group.find('.property-checkbox').prop('checked', true);
                    updateGroupInModel(label, groupId);
                });
                
                group.find('.select-none-props').click(function(e) {
                    e.preventDefault();
                    group.find('.property-checkbox').prop('checked', false);
                    updateGroupInModel(label, groupId);
                });
                
                group.find('.remove-group').click(function(e) {
                    e.preventDefault();
                    
                    const originalGroupName = group.data('original-name');
                    if (originalGroupName && embeddingGroups[label] && embeddingGroups[label][originalGroupName]) {
                        delete embeddingGroups[label][originalGroupName];
                        
                        if (Object.keys(embeddingGroups[label]).length === 0) {
                            delete embeddingGroups[label];
                        }
                        
                        updateEmbeddingGroupsField();
                    }
                    
                    group.remove();
                });
                
                updateGroupInModel(label, groupId);
                
                return group;
            }
            
            function updateGroupInModel(label, groupId) {
                const group = $(`#${groupId}`);
                const groupName = group.find('.group-name-input').val();
                
                if (!groupName) {
                    return;  
                }
                
                const checkedProps = [];
                group.find('.property-checkbox:checked').each(function() {
                    checkedProps.push($(this).val());
                });
                
                if (!embeddingGroups[label]) {
                    embeddingGroups[label] = {};
                }
                
                const originalName = group.data('original-name');
                
                if (originalName && embeddingGroups[label] && embeddingGroups[label][originalName]) {
                    delete embeddingGroups[label][originalName];
                }
                
                const newGroupName = groupName ;
                embeddingGroups[label][newGroupName] = checkedProps;
                
                group.attr('data-original-name', newGroupName);
                
                updateEmbeddingGroupsField();
                
                cleanupEmbeddingGroups();
            }
            
            addGroupBtn.click(function(e) {
                e.preventDefault();
                addNewGroup();
            });
            
            if (existingGroups && Object.keys(existingGroups).length > 0) {
                Object.entries(existingGroups).forEach(([groupFullName, props]) => {
                    let groupName = groupFullName;
                    if (groupName.endsWith('_embedding')) {
                        groupName = groupName.slice(0, -10);
                    }
                    addNewGroup(groupName, props, groupFullName);
                });
            } else {
                addNewGroup();
            }
        }
        
        if ($('.field-labels').length > 0) {
            console.log("Initializing embedding configuration UI");
            
            fetchLabels();
            
            $('.collapse').on('shown.bs.collapse', function() {
                if ($(this).find('.field-labels').length > 0) {
                    fetchLabels();
                }
            });
        }
    });
})(window.jQuery || django.jQuery);