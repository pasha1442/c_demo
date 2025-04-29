document.addEventListener('DOMContentLoaded', function() {
    // Get original fields
    const executionTypeField = document.getElementById('id_execution_type');
    const workflowField = document.getElementById('id_workflow');
    const promptNameField = document.getElementById('id_prompt_name');
    
    // Get new schema fields
    const schemaTypeField = document.getElementById('id_schema_type');
    const promptDefinedSchemaField = document.getElementById('id_prompt_defined_schema');
    const promptCreateSchemaField = document.getElementById('id_prompt_create_schema');
    
    // Check if original elements exist
    if (executionTypeField && workflowField && promptNameField) {
        // Get the parent rows
        const workflowRow = workflowField.closest('.row');
        const promptNameRow = promptNameField.closest('.row');
        
        // Function to toggle workflow field visibility
        function toggleWorkflowField() {
            const selectedValue = executionTypeField.value;
            if (selectedValue === 'workflow') {
                workflowRow.style.display = '';
            } else {
                workflowRow.style.display = 'none';
            }
        }
        
        // Function to toggle prompt_name field visibility
        function togglePromptNameField() {
            const selectedValue = executionTypeField.value;
            if (selectedValue === 'prompt') {
                promptNameRow.style.display = '';
            } else {
                promptNameRow.style.display = 'none';
            }
        }
        
        // Add change event listener using jQuery (since Django admin uses jQuery)
        $('#id_execution_type').on('change', function() {
            toggleWorkflowField();
            togglePromptNameField();
        });
        
        // Run the toggle functions on page load
        toggleWorkflowField();
        togglePromptNameField();
    }
    
    // Check if schema fields exist
    if (schemaTypeField && promptDefinedSchemaField && promptCreateSchemaField) {
        // Get the parent rows
        const promptDefinedSchemaRow = promptDefinedSchemaField.closest('.row');
        const promptCreateSchemaRow = promptCreateSchemaField.closest('.row');
        
        // Function to toggle prompt_defined_schema field visibility
        function togglePromptDefinedSchemaField() {
            const selectedValue = schemaTypeField.value;
            if (selectedValue === 'defined') {
                promptDefinedSchemaRow.style.display = '';
            } else {
                promptDefinedSchemaRow.style.display = 'none';
            }
        }
        
        // Function to toggle prompt_create_schema field visibility
        function togglePromptCreateSchemaField() {
            const selectedValue = schemaTypeField.value;
            if (selectedValue === 'create') {
                promptCreateSchemaRow.style.display = '';
            } else {
                promptCreateSchemaRow.style.display = 'none';
            }
        }
        
        // Add change event listener using jQuery
        $('#id_schema_type').on('change', function() {
            togglePromptDefinedSchemaField();
            togglePromptCreateSchemaField();
        });
        
        // Run the toggle functions on page load
        togglePromptDefinedSchemaField();
        togglePromptCreateSchemaField();
    }
});