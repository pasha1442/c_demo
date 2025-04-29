document.addEventListener('DOMContentLoaded', function() {
    const llmField = document.querySelector('#id_llm');
    const modelField = document.querySelector('#id_model');

    // Function to populate model choices
    function populateModelChoices() {
        const currentModelValue = modelField.value;
        modelField.innerHTML = '';

        const choices = {
            'openai': [['gpt-4-0125-preview', 'GPT-4'], ['gpt-3.5-turbo-1106', 'GPT-3.5'], ['gpt-4o', 'GPT-4o']],
            'google': [['gemini-1', 'Gemini-1'], ['gemini-1.5', 'Gemini-1.5']],
            'local': [['mistralai/Mistral-7B-Instruct-v0.3', 'Mistral 7B Instruct'], ['microsoft/Phi-3-mini-4k-instruct', 'Phi-3-Mini-4k-Instruct']]
        };

        const llmValue = llmField.value;
        if (choices[llmValue]) {
            choices[llmValue].forEach(function(choice) {
                const option = document.createElement('option');
                option.value = choice[0];
                option.text = choice[1];
                modelField.appendChild(option);
                if (option.value === currentModelValue) {
                    option.selected = true; 
                }
            });
        }
    }

    llmField.addEventListener('change', populateModelChoices);
    modelField.addEventListener('focus', populateModelChoices);
});
