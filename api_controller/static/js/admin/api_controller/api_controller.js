document.addEventListener('DOMContentLoaded', function() {
    const requestMediumField = document.getElementById('id_request_medium');
    const phoneNumberField = document.querySelector('[name="phone_number"]');
    const authCredsField = document.getElementById('id_auth_credentials');
    const enabledLongTermMemoryField = document.getElementById('id_enabled_long_term_memory_generation');
    const vectorStorageField = document.getElementById('id_vector_storage_for_long_term_memory');
    const summaryCheckbox = document.getElementById('id_enabled_summary_of_chat_history');
    const summaryTriggerLimitField = document.getElementById('id_summary_generation_trigger_limit');
    const messagesToKeepField = document.getElementById('id_messages_to_keep_in_chat_history_after_summarization');

    if (!requestMediumField || !phoneNumberField || !authCredsField || !summaryCheckbox || !summaryTriggerLimitField || !messagesToKeepField || !enabledLongTermMemoryField || !vectorStorageField) {
        console.error('Fields not found in the DOM');
        return;
    }

    const phoneNumberRow = phoneNumberField.closest('.row');
    const authCredsRow = authCredsField.closest('.row');
    const summaryTriggerLimitRow = summaryTriggerLimitField.closest('.row');
    const messagesToKeepRow = messagesToKeepField.closest('.row');
    const vectorStorageRow = vectorStorageField.closest('.row');

    function togglePhoneNumberField() {
        const selectedValue = requestMediumField.value;
        if (selectedValue.includes('whatsapp') || selectedValue.includes('twilio') || selectedValue.includes('waha')) {
            phoneNumberRow.style.display = '';
        } else {
            phoneNumberRow.style.display = 'none';
        }
    }

    function toggleAuthCredsField() {
        const selectedValue = requestMediumField.value;
        if (selectedValue.includes('whatsapp') || selectedValue.includes('twilio') || selectedValue.includes('waha')) {
            authCredsRow.style.display = '';
        } else {
            authCredsRow.style.display = 'none';
        }
    }

    function toggleSummaryFields() {
        if (summaryCheckbox.checked) {
            summaryTriggerLimitRow.style.display = '';
            messagesToKeepRow.style.display = '';
        } else {
            summaryTriggerLimitRow.style.display = 'none';
            messagesToKeepRow.style.display = 'none';
        }
    }

    function toggleVectorStorageField() {
        if (enabledLongTermMemoryField.checked) {
            vectorStorageRow.style.display = '';
        } else {
            vectorStorageRow.style.display = 'none';
        }
    }

    $('#id_request_medium').on('change', function() {
        togglePhoneNumberField();
        toggleAuthCredsField();
    });

    $('#id_enabled_summary_of_chat_history').on('change', function() {
        toggleSummaryFields();
    });

    enabledLongTermMemoryField.addEventListener('change', function() {
        toggleVectorStorageField();
    });

    togglePhoneNumberField();
    toggleAuthCredsField();
    toggleSummaryFields();
    toggleVectorStorageField();
});