var BASE_API_URL = "/api/v1/";

$( document ).ready(function() {
    update_company_choices();

    $("#current_company_id").change(function(){
        update_current_company();
    });
});


function get_data_from_api(api_url="", method="GET", _data={})
{

   if(!api_url)
   {return;}

    var api_url = BASE_API_URL + api_url
    return new Promise(function (resolve, reject) {
        $.ajax({
                url: api_url,
                type: method,
                data: _data,
                processData: false,
                contentType: false,
                success: function(response){
                    console.log("response.data",response.data);
                    return response.data
                },
                error: function(xhr, textStatus, error){
                    console.log("Error:", api_url, xhr, textStatus, error)
                }
            });
        });
}


function update_company_choices()
{
    var api_url = BASE_API_URL + "auth/user/get-user-wise-company-choices";
    var method="GET";
    var _data = {}
    $.ajax({
                url: api_url,
                type: method,
                data: _data,
                processData: false,
                contentType: false,
                success: function(response){
                  $('#current_company_id').empty();
                  let optionHTML = `<option value="">Select Company</option>`;
                  $('#current_company_id').append(optionHTML);
                  $.each(response.data.available_companies, function(_key, _valueObj){
                        $.each(_valueObj, function(key,valueObj){
                             let optionHTML = `<option value="${key}">
                                                    ${valueObj}
                                                </option>`;
                             $('#current_company_id').append(optionHTML);
                        });
                  });

                 $('#current_company_id').val(response.data.current_company_id);
                },
                error: function(xhr, textStatus, error){
                    console.log("Error:", api_url, xhr, textStatus, error)
                }
            });
}

function update_current_company()
{
    var api_url = BASE_API_URL + "auth/user/set-current-company";
    var method="POST";
    var csrf_token = $("#csrf_token_id").val();
    var company_id = $('#current_company_id').val();
    var _data = {"company_id": company_id}

    $.ajax({
                url: api_url,
                type: method,
                headers:{"X-CSRFToken": csrf_token},
                data: JSON.stringify(_data),
               // processData: false,
                contentType: 'application/json',
                success: function(response){
                   Swal.fire({
                      title: "Company Successfully Changed",
                      text: "Click 'Ok' to Proceed",
                      icon: "success",
                      showDenyButton: false,
                      showCancelButton: true,
                      confirmButtonText: "OK",
                      denyButtonText: `Cancel`
                    }).then((result) => {
                      /* Read more about isConfirmed, isDenied below */
                          if (result.isConfirmed) {
                                location.reload();
                          } else if (result.isDenied) {
                                location.reload();
                          }
                        });

                },
                error: function(xhr, textStatus, error){
                    console.log("Error:", api_url, xhr, textStatus, error)
                }
            });
}

function show_loader(container) {
    // Create the loader element
    let loader = document.createElement("div");
    loader.classList.add("loader");

    // Append the loader inside the specified container
    container.style.position = "relative";
    container.classList.add("loader-height")
    container.appendChild(loader);

    // Show the loader
    loader.style.display = "flex";
}

function hide_loader(container) {
    // Find the loader inside the specified container and remove it
    const loader = container.querySelector(".loader");
    if (loader) {
        loader.style.display = "none";
        container.removeChild(loader);
        container.classList.remove("loader-height")
    }
}
