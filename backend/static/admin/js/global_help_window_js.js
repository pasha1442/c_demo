function get_sidebar_model_content(api_url, params){
    return new Promise((resolve, reject) => {
        const url = new URL(endpoint, window.location.origin);

        // Append query parameters if the method is GET
        if (params) {
            Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
        }

        fetch(url, {
            method: 'GET', // Change to 'POST' if required
            headers: {
                'Content-Type': 'application/json',
            },
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json(); // Or `.json()` depending on your response type
        })
        .then(data => resolve(data))
        .catch(error => reject(error));
    });
}

function add_help_window_button(){
    const jazzyActions = document.getElementById('jazzy-actions');
    if (jazzyActions) {
        const buttonDiv = document.createElement('div');
        buttonDiv.className = 'form-group';

        const button = document.createElement('button');
        button.id = 'openHelpModalButton';
        button.type = 'button';
        button.className = 'btn btn-block btn-secondary btn-sm form-control mt-3';
        button.textContent = 'Get Help';

        // Append the button to the div
        buttonDiv.appendChild(button);

        jazzyActions.insertAdjacentElement('afterend', buttonDiv);
    }
}


$(document).ready(function () {
    add_help_window_button() // Adding help button for showing help content.

    $(document).on('click', '#openHelpModalButton', function () {
        // Create and show the modal dynamically
        $('#sidebarModal').addClass('active').fadeIn();
        const loader_container = document.querySelector('.modal-content');
        show_loader(loader_container);

        get_sidebar_model_content(endpoint, params)
            .then(response => {
                setTimeout(() => {
                    hide_loader(loader_container)
                }, 1000);
                if(response.status === 'SUCCESS'){
                    var html = response.data.sidebar_content
                    var heading = response.data.heading

                    document.getElementById('sidebarContent').innerHTML = html;
                    document.getElementById('sidebar-heading').innerHTML = heading;

                }else{
                    document.getElementById('sidebarContent').innerHTML = "<h2>No content received.</h2>";
                    const modelName = "{{ opts.model_name }}";
                    document.getElementById('sidebar-heading').innerHTML = "<h2></h2>";
                }

            })
            .catch(error => {
                hide_loader(loader_container)
                document.getElementById('sidebarContent').innerHTML = '<p>Error loading data.</p>';
        });


        // Close modal with transition
        $(document).on('click', '#closeHelpWindow', function () {
            $('#sidebarModal').removeClass('active').fadeOut();
        });

        // If adding a button in model.
//        $(document).on('click', '.close-help-model', function () {
//            $('#sidebarModal').removeClass('active').fadeOut();
//        });


    });
});
