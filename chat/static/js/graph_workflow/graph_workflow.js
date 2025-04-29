function fetch_and_update_api_controller_over_company_id() {
  var apiUrl =
    BASE_API_URL + 'api-controller/api-controller/get-available-routes/';
  var method = 'POST';
  var csrfToken = $('#csrf_token_id').val();
  var companyId = $('#current_company_id').val();
  const selectElement = document.getElementById('company_route_id');
  const loadingMessageDiv = document.getElementById('loading-message');
  const errorMessageDiv = document.getElementById('error-message');

  if (companyId === '') {
    console.error('Company ID not found');
    errorMessageDiv.innerText = 'Please select a company first.';
    errorMessageDiv.style.display = 'block';
    selectElement.style.display = 'none';
    return;
  }
  loadingMessageDiv.style.display = 'flex';
  selectElement.style.display = 'none';
  errorMessageDiv.style.display = 'none';

  var requestData = { company_id: companyId };

  $.ajax({
    url: apiUrl,
    type: method,
    headers: { 'X-CSRFToken': csrfToken },
    data: JSON.stringify(requestData),
    processData: false,
    contentType: 'application/json',
    success: function (response) {
      selectElement.innerHTML = '';
      const defaultOption = document.createElement('option');
      defaultOption.value = '';
      defaultOption.textContent = 'Select API Controller';
      defaultOption.disabled = true;
      defaultOption.selected = true;
      selectElement.appendChild(defaultOption);

      response.data.forEach((route) => {
        const option = document.createElement('option');
        option.value = route.id;
        option.textContent = route.name;
        selectElement.appendChild(option);
      });

      loadingMessageDiv.style.display = 'none';
      selectElement.style.display = 'block';

      selectElement.addEventListener('change', function () {
        if (selectElement.value) {
          defaultOption.style.display = 'none';
        } else {
          defaultOption.style.display = 'block';
        }
      });
    },
    error: function (xhr, textStatus, error) {
      console.log('Error:', apiUrl, xhr, textStatus, error);
      errorMessageDiv.innerText =
        'An error occurred while fetching API Controllers.';
      errorMessageDiv.style.display = 'block';
      loadingMessageDiv.style.display = 'none';
      selectElement.style.display = 'none';
    },
  });
}

function update_graph_json() {
  var api_url =
    BASE_API_URL + 'api-controller/api-controller/update-graph-json/';
  var method = 'POST';
  var csrf_token = $('#csrf_token_id').val();
  var route_id = $('#company_route_id').val();
  var graph_json = window.savedFlowJSON;
  var _data = {
    route_id: route_id,
    graph_json: graph_json,
  };

  $.ajax({
    url: api_url,
    type: method,
    headers: { 'X-CSRFToken': csrf_token },
    data: JSON.stringify(_data),
    processData: false,
    contentType: 'application/json',
    success: function (response) {
      window.Swal.fire('Saved!', '', 'success');
    },
    error: function (xhr, textStatus, error) {
      window.Swal.fire('Something went wrong', '', 'error');
      console.log('Error:', api_url, xhr, textStatus, error);
    },
  });
}

function get_graph_json_over_route(onSuccess) {
  var api_url =
    BASE_API_URL + 'api-controller/api-controller/get-graph-json-over-route/';
  var method = 'POST';
  var csrf_token = $('#csrf_token_id').val();
  var route_id = $('#company_route_id').val();
  var _data = {
    route_id: route_id,
  };

  $.ajax({
    url: api_url,
    type: method,
    headers: { 'X-CSRFToken': csrf_token },
    data: JSON.stringify(_data),
    processData: false,
    contentType: 'application/json',
    success: function (response) {
      window.load_graph_json_data_by_route_id = response.data.graph_json;
      if (onSuccess) {
        onSuccess(response.data.graph_json);
      }
    },
    error: function (xhr, textStatus, error) {
      window.Swal.fire('Something went wrong', '', 'error');
      console.log('Error:', api_url, xhr, textStatus, error);
    },
  });
}
  
  function save_workflow_attribute() {
    var api_url =
      BASE_API_URL + 'chat/conversations/save-workflow-attribute';
    var method = 'POST';
    var csrf_token = $('#csrf_token_id').val();
    var route_id = $('#company_route_id').val();
    var savedResponseFormatter = window.savedResponseFormatter;
  
    var _data = {
      route_id: route_id,
      savedResponseFormatter: savedResponseFormatter,
    };
  
    $.ajax({
      url: api_url,
      type: method,
      headers: { 'X-CSRFToken': csrf_token },
      data: JSON.stringify(_data),
      processData: false,
      contentType: 'application/json',
      success: function (response) {
        window.Swal.fire('Saved!', '', 'success');
      },
      error: function (xhr, textStatus, error) {
        window.Swal.fire('Something went wrong', '', 'error');
        console.log('Error:', api_url, xhr, textStatus, error);
      },
    });
  }
  
  
  function get_workflow_attributes() {
    var api_url = BASE_API_URL + 'chat/conversations/get-workflow-attributes';
    var method = 'GET';
    var csrf_token = $('#csrf_token_id').val();
    var attribute_type = window.attribute_type;

    var full_url = api_url + '?attribute_type=' + encodeURIComponent(attribute_type);
  
    return new Promise((resolve, reject) => {
      $.ajax({
        url: full_url,
        type: method,
        headers: { 'X-CSRFToken': csrf_token },
        processData: false,
        contentType: 'application/json',
        success: function (response) {
          resolve(response);  // Resolve the promise with the response
        },
        error: function (xhr, textStatus, error) {
          window.Swal.fire('Something went wrong', '', 'error');
          console.log('Error:', api_url, xhr, textStatus, error);
          reject(error);
        },
      });
    });
  }