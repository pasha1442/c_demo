document.addEventListener('DOMContentLoaded', function() {
  get_recent_sessions();
});

function get_conversation_by_client_reference_id(client_refrence_id) {
  var api_url = BASE_API_URL + 'chat/conversations/get-conversation-over-client-identifier';
  var method = 'POST';
  var csrf_token = $('#csrf_token_id').val();
  var _data = {
    client_ref_id: client_refrence_id,
  };
  const loader = document.getElementById("loader");
  const searchButton = document.getElementById("searchButton");

  $.ajax({
    url: api_url,
    type: method,
    headers: { 'X-CSRFToken': csrf_token },
    data: JSON.stringify(_data),
    processData: false,
    contentType: 'application/json',
    success: function (response) {
      loader.style.display = "none";
      searchButton.disabled = false;
      renderChatMessages(response.data);
    },
    error: function (xhr, textStatus, error) {
      searchButton.disabled = false;
      loader.style.display = "none";
      window.Swal.fire('Something went wrong', '', 'error');
      console.log('Error:', api_url, xhr, textStatus, error);
    },
  });
}

function handleSearch() {
  const searchButton = document.getElementById("searchButton");
  const loader = document.getElementById("loader");
  const searchInput = document.getElementById("searchInput").value;
  searchButton.disabled = true;
  loader.style.display = "inline-block";

  get_conversation_by_client_reference_id(searchInput);
}


function checkEnterKey(event) {
  if (event.key === "Enter") {
      event.preventDefault();
      handleSearch();
  }
}

function formatTimestamp(isoString) {
    const date = new Date(isoString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const year = date.getFullYear();
    let hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    return `${day}-${month}-${year} ${hours}:${minutes} ${ampm}`;
}

function get_recent_sessions(){
  var api_url = BASE_API_URL + 'chat/conversations/get-all-recent-sessions-list';
  var method = 'POST';
  var csrf_token = $('#csrf_token_id').val();
  var client_identifier = $('#client_identifier_id').val();
  var _data = {
    client_identifier: client_identifier,
  };

  const loader = document.getElementById("loader");
  const searchButton = document.getElementById("searchButton");

  $.ajax({
    url: api_url,
    type: method,
    headers: { 'X-CSRFToken': csrf_token },
    data: JSON.stringify(_data),
    processData: false,
    contentType: 'application/json',
    success: function (response) {
      console.log(response)
      show_recent_sessions(response?.data)
    },
    error: function (xhr, textStatus, error) {
      searchButton.disabled = false;
      loader.style.display = "none";
      window.Swal.fire('Something went wrong', '', 'error');
      console.log('Error:', api_url, xhr, textStatus, error);
    },
  });
}

function show_recent_sessions(sessionsArray){
  const recentSessionsDiv = document.querySelector('#recent-sessions');
  recentSessionsDiv.innerHTML = "";
  const listDiv = document.createElement('div');
  const ul = document.createElement('ul');

  sessionsArray.forEach(session => {
      const li = document.createElement('li');
      li.textContent = session;
      li.classList.add('session-list-data');
      li.onclick = function() {
        document.querySelector('#searchInput').value = session;
        get_conversation_by_client_reference_id(session);
      };
      ul.appendChild(li);
  });
  listDiv.appendChild(ul);
  recentSessionsDiv.appendChild(listDiv);

}


function handleTextAndImageMessage(messageContent) {
  // const imageRegex = /\.(jpg|jpeg|png|gif|bmp|webp)$/i;
  const imageRegex = /\.(jpg|jpeg|png|gif|bmp|webp)(\?.*)?$/i;

  const isImage = imageRegex.test(messageContent);

  if (isImage) {
    const imgElement = document.createElement('img');
    imgElement.src = messageContent;
    imgElement.alt = 'Image message';
    imgElement.classList.add('product-image')
    imgElement.style.maxWidth = '100px';
    // imgElement.style.maxHeight = '400px';
    imgElement.style.marginTop = '10px';

    return imgElement;
  }
  // return marked.parse(messageContent);
  let parsedContent = marked.parse(messageContent);
  const parser = new DOMParser();
  const doc = parser.parseFromString(parsedContent, 'text/html');
  const images = doc.querySelectorAll('img');
  images.forEach(img => {
    img.classList.add('product-image');
  });

  return doc.body.innerHTML;
}

function renderChatMessages(messages) {
  const chatContainer = document.querySelector('.chat-container');
  chatContainer.innerHTML = '';

  messages.forEach(message => {
    const messageDiv = document.createElement('div');
    const messageContent = document.createElement('div');
    messageContent.classList.add('chat-message');

    if (message.role === 'assistant') {
      messageDiv.classList.add('chat-left');
      messageContent.classList.add('left');
    } else if (message.role === 'user') {
      messageDiv.classList.add('chat-right');
      messageContent.classList.add('right');
    }
    messageContent.innerHTML = `<p class='message-info'><span class='message-role'>${message?.role}</span><span class='chat-date-time'>: ${formatTimestamp(message?.created_at)}</span></p>`;

    const content = handleTextAndImageMessage(message?.message);

    if (content instanceof HTMLElement) {
      messageContent.appendChild(content);
    } else {
      messageContent.innerHTML += content;
    }

    messageDiv.appendChild(messageContent);
    chatContainer.appendChild(messageDiv);
  });
  chatContainer.scrollTop = chatContainer.scrollHeight;
}
