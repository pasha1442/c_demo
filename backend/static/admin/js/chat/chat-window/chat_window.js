$(document).ready(function(){
    chat_window_hide_loader();
    load_initial_message();
    get_active_prompts();

    $("#chat_window_send_message_btn_id").click(function(){
       send_message();
    });

    $('#chat_window_textarea_id').keyup(function (event) {
        if (event.keyCode == 13) {send_message();}
    });

    $('#reload_button').click(function() {
        $('#reload_icon').removeClass('fa-sync-alt').addClass('fa-spinner fa-spin');
        setTimeout(function() {
            $('#reload_icon').removeClass('fa-spinner fa-spin').addClass('fa-sync-alt');
            get_active_prompts();
            console.log('Reloading data...');
        }, 1000);
    });

});


function chat_window_show_loader()
{
    $("#chat_window_loader_id").show();
}

function chat_window_hide_loader()
{
 $("#chat_window_loader_id").hide();
}


function load_initial_message()
{
    $('#chat_window_textarea_id').focus();
    add_left_message(name="AI", message="Hi how can assists you today ?");
}

function add_right_message(name, message)
{

       var data = {'data': {'name':name, 'message':message}}
       var related_template = _.template($("#right_message_template_id").html());
       $("#chat_window_container_id").append(related_template(data));
}

function add_left_message(name, message)
{
       var data = {'data': {'name':name, 'message':message}}
       var related_template = _.template($("#left_message_template_id").html());
       $("#chat_window_container_id").append(related_template(data));

}

function get_active_prompts()
{
    var api_url = BASE_API_URL + "api-controller/api-controller/get-available-routes/";
    var method="POST";
    var csrf_token = $("#csrf_token_id").val();

    setTimeout(function() {
        var companyId = $('#current_company_id').val();
        if (companyId === '') {
            console.error('Company ID not found');
            errorMessageDiv.innerText = 'Please select a company first.';
            errorMessageDiv.style.display = 'block';
            selectElement.style.display = 'none';
            return;
          }
        var _data = {company_id: companyId}
        $.ajax({
            url: api_url,
            type: method,
            headers: { 'X-CSRFToken': csrf_token },
            data: JSON.stringify(_data),
            processData: false,
            contentType: 'application/json',
            success: function(response) {
                if (response.data) {
                    $('#chat_window_agent_selection_id').empty();
                    $('#chat_window_agent_selection_id').append(new Option('Select API Controller', ''));
                    $.each(response.data, function(index, value) {
                        $('#chat_window_agent_selection_id').append(new Option(value.name, value.base_api_url + value.api_route +"/"));
                    });
                }
            },
            error: function(xhr, textStatus, error) {
                console.error("Error:", api_url, xhr, textStatus, error);
            }
        });
    }, 1000);
}

function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0,
            v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function send_message()
{
    var _message = $("#chat_window_textarea_id").val();
    if(_message.replace(/\s/g, '').length <= 1)
    {return}
    add_right_message(name="You", message=_message);
    $("#chat_window_textarea_id").val("");

    var api_url = $('#chat_window_agent_selection_id').val();
    var method="POST";
    var csrf_token = $("#csrf_token_id").val();
    session_id = generateUUID();
    var _data = {"mobile": '0000000000', "session_id":session_id, "text":_message}
    chat_window_show_loader();
    $.ajax({
                url: api_url,
                type: method,
                headers:{"X-CSRFToken": csrf_token},
                data: JSON.stringify(_data),
               // processData: false,
                contentType: 'application/json',
                success: function(response){
                 chat_window_hide_loader();
                  if(response.data.message)
                  {add_left_message(name="AI", message=response.data.message);}
                  $('#chat_window_parent_container_id').animate({scrollTop: $('#chat_window_parent_container_id').prop("scrollHeight")}, 500);
                },
                error: function(xhr, textStatus, error){
                    console.log("Error:", api_url, xhr, textStatus, error);
                    chat_window_hide_loader();
                }
            });
}
